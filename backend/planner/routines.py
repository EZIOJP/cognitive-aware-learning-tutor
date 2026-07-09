"""Routine templates and daily schedule application."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from backend.models.planner import PlannerBlock
from backend.models.planner_routine import PlannerRoutine
from backend.db.sqlite_utils import commit_with_retry
from backend.paths import ROOT
from backend.planner.service import (
    _minutes_between,
    _utc,
    end_from_start_and_minutes,
    wall_clock_on_date,
)

_DAY_NAMES = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def serialize_routine(r: PlannerRoutine) -> dict:
    try:
        days = json.loads(r.days_json) if r.days_json else list(_DAY_NAMES)
    except json.JSONDecodeError:
        days = list(_DAY_NAMES)
    return {
        "id": r.id,
        "title": r.title,
        "category": r.category,
        "start_time": r.start_time,
        "end_time": r.end_time,
        "duration_minutes": r.duration_minutes,
        "days": days,
        "color": r.color,
        "enabled": r.enabled,
        "sort_order": r.sort_order,
    }


def _routine_minutes(r: PlannerRoutine) -> int:
    if r.duration_minutes:
        return r.duration_minutes
    if r.end_time and r.start_time:
        sh, sm = (int(x) for x in r.start_time.split(":", 1))
        eh, em = (int(x) for x in r.end_time.split(":", 1))
        return max(1, (eh * 60 + em) - (sh * 60 + sm))
    return 30


def _routine_times_on_date(r: PlannerRoutine, target: date) -> tuple[datetime, datetime]:
    start = wall_clock_on_date(target, r.start_time)
    if r.end_time:
        end = wall_clock_on_date(target, r.end_time)
    else:
        end = end_from_start_and_minutes(start, _routine_minutes(r))
    return _utc(start), _utc(end)


def _weekday_key(d: date) -> str:
    return _DAY_NAMES[d.weekday()]


def _has_overlap(db: Session, user_id: int, start: datetime, end: datetime) -> bool:
    return (
        db.query(PlannerBlock)
        .filter(
            PlannerBlock.user_id == user_id,
            PlannerBlock.status.in_(("scheduled", "in_progress")),
            PlannerBlock.start_at < end,
            PlannerBlock.end_at > start,
        )
        .first()
        is not None
    )


def apply_routines(
    db: Session,
    user_id: int,
    *,
    target_date: date | None = None,
    skip_overlaps: bool = True,
) -> list[PlannerBlock]:
    """Create planner blocks from enabled routines for target_date (default today)."""
    target = target_date or datetime.now(timezone.utc).date()
    day_key = _weekday_key(target)

    routines = (
        db.query(PlannerRoutine)
        .filter(PlannerRoutine.user_id == user_id, PlannerRoutine.enabled.is_(True))
        .order_by(PlannerRoutine.sort_order, PlannerRoutine.id)
        .all()
    )

    created: list[PlannerBlock] = []
    for r in routines:
        try:
            days = json.loads(r.days_json) if r.days_json else list(_DAY_NAMES)
        except json.JSONDecodeError:
            days = list(_DAY_NAMES)
        norm_days = {d.strip().lower() for d in days}
        day_short = {d[:3] for d in norm_days if d}
        if day_key not in day_short and "daily" not in norm_days:
            continue

        start_at, end_at = _routine_times_on_date(r, target)
        minutes = _minutes_between(start_at, end_at)
        if skip_overlaps and _has_overlap(db, user_id, start_at, end_at):
            continue

        block = PlannerBlock(
            user_id=user_id,
            title=r.title,
            category=r.category,
            start_at=start_at,
            end_at=end_at,
            planned_minutes=minutes,
            remaining_minutes=minutes,
            status="scheduled",
            color=r.color,
        )
        db.add(block)
        created.append(block)

    commit_with_retry(db)
    for b in created:
        db.refresh(b)
    return created


def slots_to_planner_blocks(
    db: Session,
    user_id: int,
    slots: list[dict],
    *,
    target_date: date,
    skip_overlaps: bool = True,
) -> list[PlannerBlock]:
    """Import daily slots (no weekday) into planner for a specific date."""
    created: list[PlannerBlock] = []
    for slot in slots:
        start_h = slot.get("start", "09:00")
        end_h = slot.get("end")
        title = slot.get("title") or "Block"
        category = slot.get("category") or "study"
        color = slot.get("color")

        start_at = wall_clock_on_date(target_date, start_h)
        if end_h:
            end_at = wall_clock_on_date(target_date, end_h)
        else:
            dur = int(slot.get("duration_minutes") or 60)
            end_at = end_from_start_and_minutes(start_at, dur)

        minutes = _minutes_between(start_at, end_at)
        if skip_overlaps and _has_overlap(db, user_id, start_at, end_at):
            continue

        block = PlannerBlock(
            user_id=user_id,
            title=title,
            category=category,
            start_at=start_at,
            end_at=end_at,
            planned_minutes=minutes,
            remaining_minutes=minutes,
            status="scheduled",
            color=color,
        )
        db.add(block)
        created.append(block)

    commit_with_retry(db)
    for b in created:
        db.refresh(b)
    return created


DEFAULT_ROUTINES = [
    {
        "title": "Bible / devotion",
        "category": "spiritual",
        "start_time": "06:30",
        "end_time": "07:00",
        "days": list(_DAY_NAMES),
        "color": "#a78bfa",
    },
    {
        "title": "Breakfast",
        "category": "food",
        "start_time": "08:00",
        "end_time": "08:30",
        "days": list(_DAY_NAMES),
        "color": "#f59e0b",
    },
    {
        "title": "Lunch",
        "category": "food",
        "start_time": "13:00",
        "end_time": "13:45",
        "days": list(_DAY_NAMES),
        "color": "#f59e0b",
    },
    {
        "title": "Dinner",
        "category": "food",
        "start_time": "19:30",
        "end_time": "20:15",
        "days": list(_DAY_NAMES),
        "color": "#f59e0b",
    },
    {
        "title": "Bath / self-care",
        "category": "personal",
        "start_time": "21:30",
        "end_time": "22:00",
        "days": list(_DAY_NAMES),
        "color": "#06b6d4",
    },
]


def seed_default_routines(db: Session, user_id: int) -> int:
    """Insert default routines if user has none. Returns count created."""
    existing = db.query(PlannerRoutine).filter(PlannerRoutine.user_id == user_id).count()
    if existing > 0:
        return 0
    for i, spec in enumerate(DEFAULT_ROUTINES):
        db.add(
            PlannerRoutine(
                user_id=user_id,
                title=spec["title"],
                category=spec["category"],
                start_time=spec["start_time"],
                end_time=spec["end_time"],
                days_json=json.dumps(spec["days"]),
                color=spec.get("color"),
                sort_order=i,
                enabled=True,
            )
        )
    db.commit()
    return len(DEFAULT_ROUTINES)


AUTO_APPLY_STATE_PATH = ROOT / "data" / "planner_routine_auto_apply.json"


def _load_auto_apply_state() -> dict[str, str]:
    if not AUTO_APPLY_STATE_PATH.exists():
        return {}
    try:
        raw = json.loads(AUTO_APPLY_STATE_PATH.read_text(encoding="utf-8"))
        return {str(k): str(v) for k, v in raw.items()} if isinstance(raw, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _save_auto_apply_state(state: dict[str, str]) -> None:
    AUTO_APPLY_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUTO_APPLY_STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _auto_apply_key(user_id: int, target: date) -> str:
    return f"{user_id}:{target.isoformat()}"


def auto_apply_routines_today(db: Session, user_id: int) -> dict:
    """Apply enabled routines once per user per local calendar day (login hook)."""
    today = datetime.now().astimezone().date()
    state = _load_auto_apply_state()
    key = _auto_apply_key(user_id, today)
    if state.get(key):
        return {"created": 0, "skipped": True, "reason": "already_applied_today", "date": today.isoformat()}

    created = apply_routines(db, user_id, target_date=today, skip_overlaps=True)
    cutoff = today - timedelta(days=14)
    state = {k: v for k, v in state.items() if k.split(":", 1)[-1] >= cutoff.isoformat()}
    state[key] = datetime.now(timezone.utc).isoformat()
    _save_auto_apply_state(state)
    return {
        "created": len(created),
        "skipped": False,
        "date": today.isoformat(),
        "blocks": [{"id": b.id, "title": b.title} for b in created],
    }
