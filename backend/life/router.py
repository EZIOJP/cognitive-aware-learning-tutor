from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.core.auth import get_current_user
from backend.db.session import get_db
from backend.hub.services.ingest import insert_reading
from backend.hub.services.rollup import daily_payload, rebuild_daily_rollup
from backend.life.schemas import CLIENT_ALLOWED_FIELDS, LifeDailyIn, WEARABLE_OWNED_FIELDS
from backend.life.services.scoring import compute_life_score
from backend.models import LifeDailyLog, User

router = APIRouter(prefix="/api/life", tags=["life"])


def _resolve_day(day: str) -> date:
    if day in ("today", "now"):
        return date.today()
    try:
        return date.fromisoformat(day)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid date") from e


def _score_payload(row: LifeDailyLog) -> dict:
    defaults = {
        "sleep_hours": 0.0,
        "sleep_quality": 3,
        "exercise_minutes": 0,
        "water_glasses": 0,
        "meals_healthy": 0,
        "study_minutes": 0,
        "tasks_completed": 0,
        "deep_work_blocks": 0,
        "screen_time_hours": 0.0,
        "social_media_minutes": 0,
        "outdoor_minutes": 0,
        "mood_score": 3,
        "stress_level": 3,
        "meditation_minutes": 0,
    }
    payload = {}
    for key, default in defaults.items():
        val = getattr(row, key, default)
        payload[key] = default if val is None else val
    return payload


def _upsert_life_log_merge(db: Session, user_id: int, d: date, patch: dict) -> LifeDailyLog:
    row = db.query(LifeDailyLog).filter(LifeDailyLog.user_id == user_id, LifeDailyLog.date == d).first()
    if not row:
        row = LifeDailyLog(user_id=user_id, date=d)
        db.add(row)

    for key, value in patch.items():
        if value is not None:
            setattr(row, key, value)

    row.life_score = compute_life_score(**_score_payload(row))
    db.commit()
    db.refresh(row)
    return row


@router.get("/daily/{day}")
def get_life_daily(
    day: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    d = _resolve_day(day)
    row = db.query(LifeDailyLog).filter(LifeDailyLog.user_id == user.id, LifeDailyLog.date == d).first()
    if not row:
        return {"date": d.isoformat(), "life_score": 0, "empty": True, "manual_edit": False}
    return {
        "date": d.isoformat(),
        "empty": False,
        "manual_edit": False,
        "life_score": row.life_score,
        **{
            c.name: getattr(row, c.name)
            for c in LifeDailyLog.__table__.columns
            if c.name not in ("id", "user_id", "date")
        },
    }


@router.put("/daily/{day}")
def put_life_daily(
    day: str,
    body: LifeDailyIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Merge-patch only. Manual Life Tracker edits are disabled.

    Clients may only bump system fields (e.g. study_minutes from Pomodoro).
    Sleep / exercise come from wearables ingest — not this endpoint.
    """
    d = _resolve_day(day)
    provided = {k: v for k, v in body.model_dump().items() if v is not None}
    if not provided:
        raise HTTPException(status_code=400, detail="No fields to update")

    blocked = set(provided) & WEARABLE_OWNED_FIELDS
    if blocked:
        raise HTTPException(
            status_code=403,
            detail=(
                "Manual Life Tracker edits are disabled. "
                f"Sleep/exercise come from Amazfit sync only (blocked: {sorted(blocked)})."
            ),
        )

    disallowed = set(provided) - CLIENT_ALLOWED_FIELDS
    if disallowed:
        raise HTTPException(
            status_code=403,
            detail=(
                "Manual Life Tracker form is read-only. "
                f"Allowed client fields: {sorted(CLIENT_ALLOWED_FIELDS)}. "
                f"Rejected: {sorted(disallowed)}."
            ),
        )

    row = _upsert_life_log_merge(db, user.id, d, provided)

    try:
        if "study_minutes" in provided:
            insert_reading(
                db,
                user_id=user.id,
                slug="study_minutes",
                value_numeric=float(row.study_minutes),
                source_device="pomodoro",
            )
    except ValueError:
        pass

    rollup = rebuild_daily_rollup(db, user.id, d)
    return {
        "life_score": row.life_score,
        "daily": daily_payload(rollup, row),
        "log": provided,
        "manual_edit": False,
    }
