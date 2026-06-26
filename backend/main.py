"""
Primary FastAPI application entry point.

Run: python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from backend.account.router import router as account_router
from backend.behavior.router import router as behavior_router
from backend.config import get_settings
from backend.core.errors import register_exception_handlers
from backend.core.auth import ensure_default_admin
from backend.db.base import SessionLocal, engine
from backend.db.migrate import ensure_at_head
from backend.db.session import get_db
from backend.hub.router import router as hub_router
from backend.hub.services.seed import seed_reading_definitions, seed_user_plugins
from backend.insights.router import router as insights_router
from backend.math.router import router as math_router
from backend.life.router import router as life_router
from backend.models import User
from backend.models.math import MathQuestionTemplate
from backend.vocab.repository import seed_words_from_json_if_empty
from backend.vocab.router import router as vocab_router
from backend.quiz.router import router as quiz_router
from backend.transcripts.router import router as transcripts_router
from backend.corpus.router import router as corpus_router

settings = get_settings()


def _seed_math_templates(db: Session) -> None:
    if db.query(MathQuestionTemplate).count() > 0:
        return
    defaults = [
        MathQuestionTemplate(
            title="Even Addition Drill",
            topic="Arithmetic",
            operation="add",
            min_value=2,
            max_value=40,
            number_type="even",
            points=8,
        ),
        MathQuestionTemplate(
            title="Odd Multiplication Drill",
            topic="Arithmetic",
            operation="multiply",
            min_value=1,
            max_value=15,
            number_type="odd",
            points=10,
        ),
        MathQuestionTemplate(
            title="Linear Equation Basics",
            topic="Algebra",
            operation="linear_equation",
            min_value=1,
            max_value=12,
            points=14,
        ),
        MathQuestionTemplate(
            title="Combine Like Terms",
            topic="Algebra",
            operation="simplify",
            min_value=1,
            max_value=12,
            points=12,
        ),
    ]
    db.add_all(defaults)
    db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio
    import logging

    ensure_at_head()
    seed_reading_definitions(SessionLocal())
    with SessionLocal() as db:
        ensure_default_admin(db)
        _seed_math_templates(db)
        admin = db.query(User).filter_by(username="admin").first()
        if admin:
            seed_user_plugins(db, admin.id)
        demo = db.query(User).filter_by(username="demo").first()
        if demo:
            seed_user_plugins(db, demo.id)
        if settings.seed_words_on_startup:
            seed_words_from_json_if_empty(db)

    eeg_task = None
    if settings.eeg_enabled:
        try:
            from backend.eeg import service as eeg_service

            await eeg_service.start_udp_server(settings.eeg_udp_port)
            eeg_task = asyncio.create_task(eeg_service.broadcast_loop())
            logging.getLogger("backend.main").info(
                "EEG UDP on :%s, WebSocket /ws/eeg", settings.eeg_udp_port
            )
        except Exception as exc:
            logging.getLogger("backend.main").warning("EEG startup failed: %s", exc)

    yield

    if eeg_task:
        eeg_task.cancel()


app = FastAPI(
    title="Cognitive-Aware Learning Tutor API",
    version="2.0.0",
    lifespan=lifespan,
)

register_exception_handlers(app)

origins = ["*"] if settings.cors_origins == "*" else settings.cors_origins.split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(vocab_router)
app.include_router(quiz_router)
app.include_router(transcripts_router)
app.include_router(corpus_router)
app.include_router(math_router)
app.include_router(hub_router)
app.include_router(life_router)
app.include_router(insights_router)
app.include_router(behavior_router)
app.include_router(account_router)

try:
    from backend.eeg.router import router as eeg_router

    app.include_router(eeg_router)
except ImportError:
    pass


@app.get("/health")
def health():
    from backend.db.migrate import get_revision_state

    current, head = get_revision_state()
    return {
        "status": "ok",
        "database": str(engine.url),
        "schema_revision": current,
        "schema_head": head,
        "schema_ok": current == head,
        "app_env": settings.app_env,
        "eeg_enabled": settings.eeg_enabled,
        "ollama_enabled": settings.ollama_enabled,
        "dev_mode": settings.dev_mode,
    }


try:
    from backend.plugins.nutrinode_plugin import router as nutrinode_router

    app.include_router(nutrinode_router)
except ImportError as exc:
    import logging

    logging.getLogger("backend.main").warning(
        "NutriNode plugin not loaded (nutrition WebSocket will 403): %s", exc
    )
