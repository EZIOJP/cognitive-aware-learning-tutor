import json
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.models import DailyRollup, LifeDailyLog, MathAttempt, Reading, ReadingDefinition, WordProgress
from backend.config import get_settings

SEGMENT_COLORS = {
    "sleep": "#6366f1",
    "study": "#3b82f6",
    "math": "#10b981",
    "break": "#8b5cf6",
    "productive": "#14b8a6",
}


def _today_utc() -> date:
    return datetime.now(UTC).date()


def rebuild_daily_rollup(db: Session, user_id: int, day: date) -> DailyRollup:
    """Build or refresh cached rollup for Life Clock + dashboard."""
    life = (
        db.query(LifeDailyLog)
        .filter(LifeDailyLog.user_id == user_id, LifeDailyLog.date == day)
        .first()
    )

    day_start = datetime.combine(day, datetime.min.time()).replace(tzinfo=UTC)
    day_end = day_start + timedelta(days=1)

    math_count = (
        db.query(func.count(MathAttempt.id))
        .filter(
            MathAttempt.user_id == user_id,
            MathAttempt.created_at >= day_start,
            MathAttempt.created_at < day_end,
        )
        .scalar()
        or 0
    )

    vocab_events = (
        db.query(func.count(WordProgress.id))
        .filter(
            WordProgress.user_id == user_id,
            WordProgress.updated_at >= day_start,
            WordProgress.updated_at < day_end,
            WordProgress.times_asked > 0,
        )
        .scalar()
        or 0
    )

    sleep_minutes = int((life.sleep_hours * 60) if life else 0)
    study_minutes = life.study_minutes if life else 0
    productive_minutes = sleep_minutes + study_minutes + (life.exercise_minutes if life else 0)

    segments: list[dict] = []
    cursor = 0.0

    if life and life.sleep_hours > 0:
        end = min(24.0, life.sleep_hours)
        segments.append(
            {
                "label": "Sleep",
                "startHour": cursor,
                "endHour": end,
                "color": SEGMENT_COLORS["sleep"],
                "type": "sleep",
            }
        )
        cursor = end

    if study_minutes > 0:
        hours = study_minutes / 60.0
        segments.append(
            {
                "label": "Study",
                "startHour": cursor,
                "endHour": min(24.0, cursor + hours),
                "color": SEGMENT_COLORS["study"],
                "type": "study",
            }
        )
        cursor = min(24.0, cursor + hours)

    if math_count > 0:
        hours = min(2.0, math_count * 0.25)
        segments.append(
            {
                "label": "Math",
                "startHour": cursor,
                "endHour": min(24.0, cursor + hours),
                "color": SEGMENT_COLORS["math"],
                "type": "math",
            }
        )

    stats = {
        "life_score": life.life_score if life else 0,
        "math_attempts": math_count,
        "vocab_events": vocab_events,
    }

    rollup = (
        db.query(DailyRollup)
        .filter(DailyRollup.user_id == user_id, DailyRollup.date == day)
        .first()
    )
    if not rollup:
        rollup = DailyRollup(user_id=user_id, date=day)
        db.add(rollup)

    rollup.segments_json = json.dumps(segments)
    rollup.productive_minutes = productive_minutes
    rollup.sleep_minutes = sleep_minutes
    rollup.vocab_events = vocab_events
    rollup.math_attempts = math_count
    rollup.stats_json = json.dumps(stats)
    db.commit()
    db.refresh(rollup)
    return rollup


def daily_payload(rollup: DailyRollup, life: LifeDailyLog | None) -> dict:
    now = datetime.now(UTC)
    current_hour = now.hour + now.minute / 60 + now.second / 3600
    segments = json.loads(rollup.segments_json or "[]")

    return {
        "date": rollup.date.isoformat(),
        "segments": segments,
        "productive_minutes": rollup.productive_minutes,
        "sleep_minutes": rollup.sleep_minutes,
        "vocab_events": rollup.vocab_events,
        "math_attempts": rollup.math_attempts,
        "stats": json.loads(rollup.stats_json or "{}"),
        "life_score": life.life_score if life else 0,
        "time_left_hours": max(0, 24 - current_hour),
        "percent_elapsed": round((current_hour / 24) * 100, 1),
        "current_hour": current_hour,
    }
