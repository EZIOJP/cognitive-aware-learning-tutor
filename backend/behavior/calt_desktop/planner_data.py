"""Local planner CRUD for CALT Desktop (same DB as /api/planner)."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from backend.db.base import SessionLocal
from backend.models.planner import PlannerBlock
from backend.planner.service import (
    _minutes_between,
    _utc,
    end_from_start_and_minutes,
    local_day_bounds_utc,
    local_tz,
    serialize_block,
)


def _fmt_local(iso: str | None) -> str:
    if not iso:
        return "—"
    raw = iso.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return iso
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone().strftime("%H:%M")


def _enrich(row: dict[str, Any]) -> dict[str, Any]:
    row["start_local"] = _fmt_local(row.get("start_at"))
    row["end_local"] = _fmt_local(row.get("end_at"))
    return row


def local_datetime(day: date, hour: int, minute: int) -> datetime:
    """Wall-clock on *day* in host TZ → UTC for storage."""
    local = datetime(day.year, day.month, day.day, hour, minute, tzinfo=local_tz())
    return _utc(local)


def blocks_for_day(user_id: int, day: date | None = None) -> list[dict[str, Any]]:
    if not user_id:
        return []
    day = day or date.today()
    start, end = local_day_bounds_utc(day)
    return blocks_between(user_id, start, end)


def blocks_between(user_id: int, start_utc: datetime, end_utc: datetime) -> list[dict[str, Any]]:
    if not user_id:
        return []
    db = SessionLocal()
    try:
        rows = (
            db.query(PlannerBlock)
            .filter(
                PlannerBlock.user_id == user_id,
                PlannerBlock.start_at < end_utc,
                PlannerBlock.end_at > start_utc,
                PlannerBlock.status.notin_(("cancelled", "rolled")),
            )
            .order_by(PlannerBlock.start_at.asc())
            .all()
        )
        return [_enrich(serialize_block(b)) for b in rows]
    finally:
        db.close()


def blocks_for_range(user_id: int, range_start: date, horizon_days: int) -> list[dict[str, Any]]:
    start, _ = local_day_bounds_utc(range_start)
    _, end = local_day_bounds_utc(range_start + timedelta(days=max(1, horizon_days) - 1))
    return blocks_between(user_id, start, end)


def create_block(
    user_id: int,
    *,
    title: str,
    category: str,
    day: date,
    start_hour: int,
    start_minute: int,
    end_hour: int,
    end_minute: int,
) -> dict[str, Any]:
    start = local_datetime(day, start_hour, start_minute)
    end = local_datetime(day, end_hour, end_minute)
    if end <= start:
        end = end + timedelta(days=1)
    minutes = _minutes_between(start, end)
    db = SessionLocal()
    try:
        block = PlannerBlock(
            user_id=user_id,
            title=title.strip() or "Untitled",
            category=category or "study",
            start_at=start,
            end_at=end,
            planned_minutes=minutes,
            remaining_minutes=minutes,
            status="scheduled",
        )
        db.add(block)
        db.commit()
        db.refresh(block)
        return _enrich(serialize_block(block))
    finally:
        db.close()


def update_block(
    user_id: int,
    block_id: int,
    *,
    title: str | None = None,
    category: str | None = None,
    day: date | None = None,
    start_hour: int | None = None,
    start_minute: int | None = None,
    end_hour: int | None = None,
    end_minute: int | None = None,
) -> dict[str, Any]:
    db = SessionLocal()
    try:
        block = (
            db.query(PlannerBlock)
            .filter(PlannerBlock.id == block_id, PlannerBlock.user_id == user_id)
            .first()
        )
        if block is None:
            raise KeyError(f"Block {block_id} not found")

        if title is not None:
            block.title = title.strip() or block.title
        if category is not None:
            block.category = category

        if day is not None and start_hour is not None and start_minute is not None:
            block.start_at = local_datetime(day, start_hour, start_minute)
        if day is not None and end_hour is not None and end_minute is not None:
            block.end_at = local_datetime(day, end_hour, end_minute)
            if block.end_at <= block.start_at:
                block.end_at = block.end_at + timedelta(days=1)
            block.planned_minutes = _minutes_between(block.start_at, block.end_at)
            if block.status == "scheduled":
                block.remaining_minutes = block.planned_minutes

        db.commit()
        db.refresh(block)
        return _enrich(serialize_block(block))
    finally:
        db.close()


def delete_block(user_id: int, block_id: int) -> None:
    db = SessionLocal()
    try:
        block = (
            db.query(PlannerBlock)
            .filter(PlannerBlock.id == block_id, PlannerBlock.user_id == user_id)
            .first()
        )
        if block is None:
            raise KeyError(f"Block {block_id} not found")
        db.delete(block)
        db.commit()
    finally:
        db.close()


def apply_routines_for_day(user_id: int, day: date | None = None) -> dict[str, Any]:
    """Materialize enabled routines onto the calendar day (skip overlaps)."""
    from backend.planner.routines import apply_routines

    day = day or date.today()
    db = SessionLocal()
    try:
        created = apply_routines(db, user_id, target_date=day, skip_overlaps=True)
        db.commit()
        return {"created": len(created), "block_ids": [b.id for b in created]}
    finally:
        db.close()
