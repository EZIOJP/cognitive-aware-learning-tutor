"""Thin hooks from real study/morning events → break_reward (Desktop Tracker v2c Task 6).

§0: Q1 A4 incubation · Q2 B5 earn · Q5 E1 spend (dashboard).
Idempotent same-day reason guards for bible / plan / daily_goal.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from backend.behavior.break_reward import (
    REASON_BIBLE,
    REASON_DAILY_GOAL,
    REASON_PLAN,
    earn,
    load_config,
    start_incubation,
)


def _session(db: Session | None) -> tuple[Session, bool]:
    if db is not None:
        return db, False
    from backend.db.base import SessionLocal

    return SessionLocal(), True


def reason_earned_today(
    user_id: int,
    reason: str,
    *,
    db: Session | None = None,
    now: datetime | None = None,
) -> bool:
    """True when this reason already has a positive ledger row for the local day."""
    from backend.models.break_reward import RewardLedger
    from backend.planner.service import local_tz

    reason_key = str(reason or "").strip()
    if not reason_key:
        return False

    dt = now if now is not None else datetime.now(local_tz())
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=local_tz())
    else:
        dt = dt.astimezone(local_tz())
    day_start = datetime(dt.year, dt.month, dt.day, tzinfo=local_tz()).astimezone(UTC)
    day_end = day_start + timedelta(days=1)

    session, own = _session(db)
    try:
        rows = (
            session.query(RewardLedger)
            .filter(
                RewardLedger.user_id == int(user_id),
                RewardLedger.reason == reason_key,
                RewardLedger.delta_minutes > 0,
            )
            .all()
        )
        for row in rows:
            created = row.created_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=UTC)
            else:
                created = created.astimezone(UTC)
            if day_start <= created < day_end:
                return True
        return False
    finally:
        if own:
            session.close()


def earn_once(
    user_id: int,
    reason: str,
    *,
    db: Session | None = None,
    now: datetime | None = None,
    config: dict[str, Any] | None = None,
    ref_id: str | None = None,
) -> dict[str, Any]:
    """Credit earn rates once per reason per local day (then daily cap still applies)."""
    if reason_earned_today(int(user_id), reason, db=db, now=now):
        from backend.behavior.break_reward import balance, daily_earned

        cfg = config if config is not None else load_config()
        return {
            "credited": 0,
            "balance": balance(int(user_id), db=db),
            "daily_earned": daily_earned(int(user_id), db=db, now=now),
            "daily_cap": int(cfg.get("daily_earn_cap") or 0),
            "reason": str(reason),
            "already": True,
        }
    return earn(
        int(user_id),
        reason,
        db=db,
        now=now,
        config=config,
        ref_id=ref_id,
    )


def on_bible_done(
    user_id: int,
    *,
    db: Session | None = None,
    now: datetime | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return earn_once(int(user_id), REASON_BIBLE, db=db, now=now, config=config)


def on_plan_confirm(
    user_id: int,
    *,
    db: Session | None = None,
    now: datetime | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return earn_once(int(user_id), REASON_PLAN, db=db, now=now, config=config)


def maybe_earn_daily_goal(
    user_id: int,
    productive_minutes: int | float | None = None,
    daily_goal_minutes: int | float | None = None,
    *,
    db: Session | None = None,
    now: datetime | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """When productive crosses daily goal, credit once. Returns None if not met."""
    try:
        prod = int(productive_minutes or 0)
        goal = int(daily_goal_minutes or 0)
    except (TypeError, ValueError):
        return None
    if goal <= 0 or prod < goal:
        return None
    return earn_once(int(user_id), REASON_DAILY_GOAL, db=db, now=now, config=config)


def maybe_start_incubation_after_focus(
    user_id: int,
    *,
    trigger: str,
    source_session_id: str | None = None,
    productive_streak_min: float | int | None = None,
    work_minutes: int | None = None,
    db: Session | None = None,
    now: datetime | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Q1 A4 — start incubation on study-block end or productive streak ≥ work_minutes.

    Returns status dict, or None if not applicable / rate-limited.
    """
    cfg = config if config is not None else load_config()
    work = int(work_minutes if work_minutes is not None else cfg.get("work_minutes") or 45)
    work = max(1, work)
    kind = str(trigger or "").strip().lower()

    if kind == "study_block_end":
        return start_incubation(
            int(user_id),
            source_session_id=source_session_id,
            db=db,
            now=now,
            config=cfg,
        )

    if kind == "productive_streak":
        try:
            streak = float(productive_streak_min or 0)
        except (TypeError, ValueError):
            streak = 0.0
        if streak < work:
            return None
        return start_incubation(
            int(user_id),
            source_session_id=source_session_id or f"streak:{int(streak)}",
            db=db,
            now=now,
            config=cfg,
        )

    return None
