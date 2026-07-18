"""
Primary FastAPI application entry point.

Run: python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
"""

from backend.core.log_setup import setup_logging

setup_logging()

from contextlib import asynccontextmanager
import logging
import time

from fastapi import FastAPI, Request
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
from backend.core.system_router import router as system_router
from backend.core.llm_router import router as llm_router
from backend.app.router import router as app_router
from backend.timetable.router import router as timetable_router
from backend.planner.router import router as planner_router
from backend.wearables.router import router as wearables_router
from backend.journal.router import router as journal_router
from backend.behavior.classification_router import router as classification_router

settings = get_settings()
_request_log = logging.getLogger("backend.request")


def _install_windows_disconnect_filter() -> None:
    """Quiet harmless Proactor disconnect noise on Windows websocket closes."""
    import asyncio

    loop = asyncio.get_running_loop()
    previous = loop.get_exception_handler()
    log = logging.getLogger("backend.websocket")

    def _handler(loop, context):
        exc = context.get("exception")
        if isinstance(exc, ConnectionResetError) and getattr(exc, "winerror", None) == 10054:
            log.debug("Ignored websocket/client disconnect: %s", exc)
            return
        if previous:
            previous(loop, context)
        else:
            loop.default_exception_handler(context)

    loop.set_exception_handler(_handler)


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

    _install_windows_disconnect_filter()
    ensure_at_head()
    seed_reading_definitions(SessionLocal())
    with SessionLocal() as db:
        from backend.core.auth import merge_demo_planner_into_solo

        ensure_default_admin(db)
        if settings.solo_local_user:
            moved = merge_demo_planner_into_solo(db)
            if moved:
                logging.getLogger("backend.main").info(
                    "solo_local_user: merged %s demo planner blocks into admin",
                    moved,
                )
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


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    path = request.url.path
    skip = path.startswith("/ws") or path == "/health"
    try:
        response = await call_next(request)
    except Exception:
        elapsed_ms = (time.perf_counter() - start) * 1000
        if not skip:
            _request_log.exception(
                "%s %s failed after %.0fms",
                request.method,
                path,
                elapsed_ms,
            )
        raise
    elapsed_ms = (time.perf_counter() - start) * 1000
    if not skip and (response.status_code >= 400 or elapsed_ms > 3000):
        _request_log.warning(
            "%s %s -> %s (%.0fms)",
            request.method,
            path,
            response.status_code,
            elapsed_ms,
        )
    return response


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
app.include_router(system_router)
app.include_router(llm_router)
app.include_router(timetable_router)
app.include_router(planner_router)
app.include_router(wearables_router)
app.include_router(journal_router)
app.include_router(classification_router)
app.include_router(app_router)

try:
    from backend.eeg.router import router as eeg_router

    app.include_router(eeg_router)
except ImportError:
    pass


@app.get("/health")
def health():
    from backend.db.migrate import get_revision_state

    current, head = get_revision_state()
    route_paths = {getattr(r, "path", "") for r in app.routes if hasattr(r, "path")}
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
        "features": {
            "planner": "/api/planner/blocks" in route_paths,
            "behavior_desktop_timeline": "/api/behavior/desktop-timeline" in route_paths,
            "behavior_tracker_health": "/api/behavior/tracker-health" in route_paths,
            "calt_android_download": "/api/app/calt-android/download" in route_paths,
        },
    }


try:
    from backend.plugins.nutrinode_plugin import router as nutrinode_router

    app.include_router(nutrinode_router)
except ImportError as exc:
    import logging

    logging.getLogger("backend.main").warning(
        "NutriNode plugin not loaded (nutrition WebSocket will 403): %s", exc
    )
