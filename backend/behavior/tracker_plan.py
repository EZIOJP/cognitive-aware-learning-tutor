"""Read current / next planner block for system tray (shared SQLite)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from backend.db.base import SessionLocal
from backend.models.planner import PlannerBlock

_ACTIVE_STATUSES = ("scheduled", "in_progress", "done")


@dataclass(frozen=True)
class PlanBlockSnapshot:
    title: str
    category: str
    minutes_left: int
    start_at: datetime
    end_at: datetime


@dataclass(frozen=True)
class PlanContext:
    current: PlanBlockSnapshot | None
    next: PlanBlockSnapshot | None


def _utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _local_day_bounds_utc(now: datetime | None = None) -> tuple[datetime, datetime]:
    now_utc = _utc(now or datetime.now(timezone.utc))
    local = now_utc.astimezone()
    start_local = local.replace(hour=0, minute=0, second=0, microsecond=0)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def _snapshot(block: PlannerBlock, now: datetime) -> PlanBlockSnapshot:
    end = _utc(block.end_at)
    mins_left = max(0, int((end - now).total_seconds() // 60))
    return PlanBlockSnapshot(
        title=block.title,
        category=block.category,
        minutes_left=mins_left,
        start_at=_utc(block.start_at),
        end_at=end,
    )


@dataclass(frozen=True)
class DayBlockRow:
    title: str
    category: str
    start_at: datetime
    end_at: datetime
    status: str
    is_current: bool
    minutes_left: int


def fetch_today_schedule(
    user_id: int,
    now: datetime | None = None,
    *,
    db: Session | None = None,
) -> list[DayBlockRow]:
    """All active planner blocks for today, ordered by start time."""
    now_utc = _utc(now or datetime.now(timezone.utc))
    day_start, day_end = _local_day_bounds_utc(now_utc)

    own_session = db is None
    session = db or SessionLocal()
    try:
        blocks = (
            session.query(PlannerBlock)
            .filter(
                PlannerBlock.user_id == user_id,
                PlannerBlock.start_at < day_end,
                PlannerBlock.end_at > day_start,
                PlannerBlock.status.in_(_ACTIVE_STATUSES),
            )
            .order_by(PlannerBlock.start_at)
            .all()
        )
    finally:
        if own_session:
            session.close()

    rows: list[DayBlockRow] = []
    for block in blocks:
        start = _utc(block.start_at)
        end = _utc(block.end_at)
        is_current = start <= now_utc < end
        mins_left = max(0, int((end - now_utc).total_seconds() // 60)) if is_current else 0
        rows.append(
            DayBlockRow(
                title=block.title,
                category=block.category,
                start_at=start,
                end_at=end,
                status=block.status,
                is_current=is_current,
                minutes_left=mins_left,
            )
        )
    return rows


def fetch_plan_context(
    user_id: int,
    now: datetime | None = None,
    *,
    db: Session | None = None,
) -> PlanContext:
    """Return the active planner block now and the next block later today."""
    now_utc = _utc(now or datetime.now(timezone.utc))
    day_start, day_end = _local_day_bounds_utc(now_utc)

    own_session = db is None
    session = db or SessionLocal()
    try:
        blocks = (
            session.query(PlannerBlock)
            .filter(
                PlannerBlock.user_id == user_id,
                PlannerBlock.start_at < day_end,
                PlannerBlock.end_at > day_start,
                PlannerBlock.status.in_(_ACTIVE_STATUSES),
            )
            .order_by(PlannerBlock.start_at)
            .all()
        )
    finally:
        if own_session:
            session.close()

    current: PlanBlockSnapshot | None = None
    nxt: PlanBlockSnapshot | None = None

    for block in blocks:
        start = _utc(block.start_at)
        end = _utc(block.end_at)
        if start <= now_utc < end:
            current = _snapshot(block, now_utc)
        elif start > now_utc and nxt is None:
            nxt = _snapshot(block, now_utc)

    return PlanContext(current=current, next=nxt)
