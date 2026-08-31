"""Compact productivity snapshot for day-status (mobile / watch / hub board)."""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from backend.behavior.goals_alerts import build_goals_status
from backend.behavior.productivity_pulse import attach_pulse
from backend.behavior.stats_aggregate import aggregate_session_rows, desktop_sessions_payload
from backend.behavior.time_fmt import format_hours_mins


def _tracker_user_ids(db: Session, user_id: int) -> list[int]:
    try:
        from backend.models import User
        from backend.timetable.tracker_query import tracker_user_ids

        user = db.query(User).filter(User.id == user_id).first()
        return tracker_user_ids(db, user) if user else [user_id]
    except Exception:
        return [user_id]


def _sessions_for_day(db: Session, user_ids: list[int], day: date, *, user_id: int) -> tuple[list[dict[str, Any]], int]:
    from backend.behavior.category_scores import load_score_map
    from backend.behavior.productivity_policy import load_policy_dict
    from backend.behavior.session_merge import merge_tracked_rows
    from backend.models.timetable import TrackedSession
    from backend.planner.service import local_day_bounds_utc

    scores = load_score_map(db)
    policy = load_policy_dict(db, user_id)
    start, end = local_day_bounds_utc(day)
    rows = (
        db.query(TrackedSession)
        .filter(
            TrackedSession.user_id.in_(user_ids),
            TrackedSession.source.in_(("desktop_tracker", "extension", "calt_spa")),
            TrackedSession.start_time >= start,
            TrackedSession.start_time < end,
        )
        .order_by(TrackedSession.start_time)
        .all()
    )
    rows = merge_tracked_rows(rows)
    buckets, total = aggregate_session_rows(rows, scores=scores, policy=policy)
    sessions = desktop_sessions_payload(buckets)
    return sessions, total


def _focus_quality_compact(db: Session, user_ids: list[int], day: date, *, user_id: int) -> dict[str, Any]:
    from backend.behavior.category_scores import load_score_map, serialize_tracked_session
    from backend.behavior.focus_quality import compute_focus_quality
    from backend.behavior.productivity_policy import load_policy_dict
    from backend.behavior.session_merge import merge_tracked_rows
    from backend.models.planner import PlannerBlock
    from backend.models.timetable import TrackedSession
    from backend.planner.service import local_day_bounds_utc

    start, end = local_day_bounds_utc(day)
    blocks = (
        db.query(PlannerBlock)
        .filter(
            PlannerBlock.user_id == user_id,
            PlannerBlock.start_at >= start,
            PlannerBlock.start_at < end,
            PlannerBlock.status.notin_(("cancelled", "rolled")),
        )
        .all()
    )
    intervals = [(b.start_at, b.end_at) for b in blocks if b.start_at and b.end_at]
    rows = (
        db.query(TrackedSession)
        .filter(
            TrackedSession.user_id.in_(user_ids),
            TrackedSession.source.in_(("desktop_tracker", "extension", "calt_spa")),
            TrackedSession.start_time >= start,
            TrackedSession.start_time < end,
        )
        .all()
    )
    rows = merge_tracked_rows(rows)
    scores = load_score_map(db)
    policy = load_policy_dict(db, user_id)
    serialized = [serialize_tracked_session(r, scores, policy) for r in rows]
    result = compute_focus_quality(serialized, planned_intervals=intervals)
    return {
        "score": result.get("score"),
        "label": result.get("label"),
        "switches": result.get("switches"),
        "on_plan_minutes": result.get("on_plan_minutes"),
    }


def _weekly_snippet(db: Session, user_ids: list[int], *, user_id: int) -> dict[str, Any]:
    from backend.behavior.weekly_digest import build_weekly_digest

    digest = build_weekly_digest(db, user_ids, user_id=user_id, days=7)
    drains = digest.get("top_drains") or []
    return {
        "avg_pulse": digest.get("avg_pulse"),
        "goal_met_days": digest.get("goal_met_days"),
        "tracked_days": digest.get("tracked_days"),
        "top_drain": drains[0]["label"] if drains else None,
        "top_drain_seconds": drains[0]["seconds"] if drains else 0,
    }


def build_productivity_snapshot(db: Session, user_id: int, *, day: date | None = None) -> dict[str, Any]:
    """Pulse, goals, focus quality, weekly snippet — one mobile-friendly block."""
    d = day or date.today()
    user_ids = _tracker_user_ids(db, user_id)
    sessions, total = _sessions_for_day(db, user_ids, d, user_id=user_id)
    pulse_payload = attach_pulse({"sessions": sessions, "total_seconds": total, "date": d.isoformat()})

    goals = build_goals_status(db, user_ids, d, user_id=user_id)
    primary_goal = goals["goals"][0] if goals.get("goals") else {}
    active_alerts = [
        {
            "id": a.get("id"),
            "label": a.get("label"),
            "triggered": bool(a.get("triggered")),
            "current_seconds": a.get("current_seconds"),
            "max_seconds": a.get("max_seconds"),
        }
        for a in (goals.get("alerts") or [])
        if a.get("triggered") or int(a.get("current_seconds") or 0) > 0
    ]

    focus = _focus_quality_compact(db, user_ids, d, user_id=user_id)
    weekly = _weekly_snippet(db, user_ids, user_id=user_id)

    from backend.behavior.study_mode_nudge import study_nudge_active, study_nudge_until

    nudge_until = study_nudge_until()
    nudge_active = study_nudge_active()

    productive_s = int(pulse_payload.get("productive_seconds") or goals.get("productive_seconds") or 0)
    distracting_s = int(pulse_payload.get("distracting_seconds") or 0)

    return {
        "date": d.isoformat(),
        "pulse": int(pulse_payload.get("pulse") or 0),
        "pulse_label": pulse_payload.get("pulse_label") or "No data",
        "productive_seconds": productive_s,
        "productive_label": format_hours_mins(productive_s // 60) if productive_s else "0 mins",
        "distracting_seconds": distracting_s,
        "distracting_label": format_hours_mins(distracting_s // 60) if distracting_s else "0 mins",
        "total_seconds": int(pulse_payload.get("total_seconds") or goals.get("total_seconds") or 0),
        "goal_pct": int(primary_goal.get("pct") or 0),
        "goal_met": bool(primary_goal.get("met")),
        "goal_target_seconds": int(primary_goal.get("target_seconds") or 0),
        "goals": goals.get("goals") or [],
        "alerts": active_alerts,
        "focus_quality": focus,
        "weekly": weekly,
        "study_mode_nudge": {
            "active": nudge_active,
            "until": nudge_until.isoformat() if nudge_until else None,
        },
    }
