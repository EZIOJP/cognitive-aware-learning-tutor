from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.core.auth import get_current_user
from backend.db.session import get_db
from backend.hub.services.rollup import rebuild_daily_rollup
from backend.models import LifeDailyLog, User

router = APIRouter(prefix="/api/insights", tags=["insights"])


class ReviewOut(BaseModel):
    comments: str
    next_steps: list[str]
    goals: list[str]
    overall_performance: str
    source: str = "template"


@router.get("/daily")
def insights_daily(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    d = date.today()
    life = db.query(LifeDailyLog).filter(LifeDailyLog.user_id == user.id, LifeDailyLog.date == d).first()
    rollup = rebuild_daily_rollup(db, user.id, d)

    performance = "needs-improvement"
    if life and life.life_score >= 80:
        performance = "excellent"
    elif life and life.life_score >= 55:
        performance = "good"

    return {
        "date": d.isoformat(),
        "life_score": life.life_score if life else 0,
        "study_minutes": life.study_minutes if life else 0,
        "productive_minutes": rollup.productive_minutes,
        "sleep_minutes": rollup.sleep_minutes,
        "vocab_events": rollup.vocab_events,
        "math_attempts": rollup.math_attempts,
        "overall_performance": performance,
    }


def _template_review(data: dict) -> ReviewOut:
    perf = data["overall_performance"]
    comments = {
        "excellent": "Strong day — keep your current rhythm.",
        "good": "Solid progress; small tweaks to sleep or focus could help.",
        "needs-improvement": "Take a breath — shorten sessions and protect sleep tonight.",
    }[perf]
    steps = []
    if data["sleep_minutes"] < 420:
        steps.append("Aim for 7+ hours of sleep tonight.")
    if data["productive_minutes"] < 120:
        steps.append("Schedule a 2-hour deep-work block with the browser extension on.")
    if data["study_minutes"] < 60:
        steps.append("Block 25 minutes for focused study.")
    if data["vocab_events"] == 0:
        steps.append("Run one GRE vocab cycle to keep retention sharp.")
    if data["math_attempts"] == 0:
        steps.append("Complete one math practice set (enable Math Tutor plugin).")
    ocr_samples = data.get("ocr_samples", 0)
    if ocr_samples and ocr_samples < 20:
        steps.append(f"Keep training handwriting — {ocr_samples} OCR samples logged so far.")
    if not steps:
        steps.append("Maintain today's habits — metrics look balanced.")

    return ReviewOut(
        comments=comments,
        next_steps=steps,
        goals=["Protect sleep", "One focused study block", "Track mood daily"],
        overall_performance=perf,
        source="template",
    )


@router.post("/review", response_model=ReviewOut)
async def insights_review(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    data = insights_daily(db=db, user=user)
    from backend.math.training_log import training_stats_for_hub

    data = {**data, **training_stats_for_hub(user.id)}

    from backend.integrations.nim_client import nim_available

    if nim_available():
        try:
            from backend.hub.services.gemma_review import generate_daily_review

            gemma = await generate_daily_review(data, user_id=user.id)
            return ReviewOut(**gemma)
        except Exception:
            pass

    return _template_review(data)
