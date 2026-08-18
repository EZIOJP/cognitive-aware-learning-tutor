"""Planner block business logic — remaining time, roll-forward, slot suggestion."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from backend.models.planner import PlannerBlock
from backend.behavior.time_fmt import optional_minutes_label

_DAY_MAP = {
    "mon": 0,
    "tue": 1,
    "wed": 2,
    "thu": 3,
    "fri": 4,
    "sat": 5,
    "sun": 6,
}


def _utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def local_tz():
    """Host timezone for wall-clock schedule times (local-first single user)."""
    return datetime.now().astimezone().tzinfo


def local_day_bounds_utc(day: date) -> tuple[datetime, datetime]:
    """UTC half-open [start, end) spanning one host-local calendar day."""
    start_local = datetime(day.year, day.month, day.day, tzinfo=local_tz())
    end_local = start_local + timedelta(days=1)
    return _utc(start_local), _utc(end_local)


def wall_clock_on_date(target: date, hhmm: str) -> datetime:
    """Parse HH:MM on a calendar date in local time; return UTC for storage."""
    hour, minute = (int(x) for x in hhmm.split(":", 1))
    local = datetime(target.year, target.month, target.day, hour, minute, tzinfo=local_tz())
    return _utc(local)


def iso_utc(dt: datetime | None) -> str | None:
    """Serialize DB datetimes (naive UTC) for browser clients."""
    if dt is None:
        return None
    return _utc(dt).isoformat().replace("+00:00", "Z")


def _minutes_between(start: datetime, end: datetime) -> int:
    return max(1, int((_utc(end) - _utc(start)).total_seconds() // 60))


def end_from_start_and_minutes(start: datetime, minutes: int) -> datetime:
    return _utc(start) + timedelta(minutes=minutes)


def serialize_block(block: PlannerBlock) -> dict:
    return {
        "id": block.id,
        "title": block.title,
        "category": block.category,
        "start_at": iso_utc(block.start_at),
        "end_at": iso_utc(block.end_at),
        "planned_minutes": block.planned_minutes,
        "planned_label": optional_minutes_label(block.planned_minutes),
        "remaining_minutes": block.remaining_minutes,
        "remaining_label": optional_minutes_label(block.remaining_minutes),
        "status": block.status,
        "rolled_from_id": block.rolled_from_id,
        "roll_count": block.roll_count,
        "task_id": block.task_id,
        "color": block.color,
        "created_at": block.created_at.isoformat() if block.created_at else None,
    }


def suggest_next_slot(
    db: Session,
    user_id: int,
    *,
    after: datetime | None = None,
    duration_minutes: int,
) -> datetime:
    """Next free hour-aligned slot today, else tomorrow 09:00 local UTC."""
    now = _utc(after or datetime.now(timezone.utc))
    candidate = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    if candidate <= now:
        candidate += timedelta(hours=1)

    for _ in range(48):
        cand_end = candidate + timedelta(minutes=duration_minutes)
        overlap = (
            db.query(PlannerBlock)
            .filter(
                PlannerBlock.user_id == user_id,
                PlannerBlock.status.in_(("scheduled", "in_progress")),
                PlannerBlock.start_at < cand_end,
                PlannerBlock.end_at > candidate,
            )
            .first()
        )
        if overlap is None:
            return candidate
        candidate += timedelta(hours=1)

    tomorrow = (now + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
    return tomorrow


def complete_block(
    block: PlannerBlock,
    *,
    minutes_spent: int | None = None,
) -> PlannerBlock:
    if block.status in ("done", "rolled", "cancelled"):
        return block

    if minutes_spent is not None:
        block.remaining_minutes = max(0, block.remaining_minutes - minutes_spent)
    else:
        block.remaining_minutes = 0

    if block.remaining_minutes <= 0:
        block.remaining_minutes = 0
        block.status = "done"
    else:
        block.end_at = end_from_start_and_minutes(block.start_at, block.remaining_minutes)

    return block


def roll_forward_block(
    db: Session,
    block: PlannerBlock,
    *,
    new_start: datetime | None = None,
) -> PlannerBlock:
    if block.remaining_minutes <= 0:
        block.status = "done"
        return block

    block.status = "rolled"
    start = _utc(new_start) if new_start else suggest_next_slot(
        db,
        block.user_id,
        after=datetime.now(timezone.utc),
        duration_minutes=block.remaining_minutes,
    )
    end = end_from_start_and_minutes(start, block.remaining_minutes)

    new_block = PlannerBlock(
        user_id=block.user_id,
        title=block.title,
        category=block.category,
        start_at=start,
        end_at=end,
        planned_minutes=block.planned_minutes,
        remaining_minutes=block.remaining_minutes,
        status="scheduled",
        rolled_from_id=block.id,
        roll_count=block.roll_count + 1,
        task_id=block.task_id,
        color=block.color,
    )
    db.add(new_block)
    db.flush()
    return new_block


def parse_day_to_weekday(day: str) -> int:
    d = day.strip().lower()[:3]
    if d.isdigit():
        return int(d) % 7
    return _DAY_MAP.get(d, 0)


def slot_datetime(week_start: datetime, day: str, hhmm: str) -> datetime:
    """Map weekly slot to absolute datetime in week starting week_start (Monday)."""
    base_local = _utc(week_start).astimezone(local_tz()).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    base_local = base_local - timedelta(days=base_local.weekday())
    offset = parse_day_to_weekday(day)
    target = (base_local + timedelta(days=offset)).date()
    return wall_clock_on_date(target, hhmm)
