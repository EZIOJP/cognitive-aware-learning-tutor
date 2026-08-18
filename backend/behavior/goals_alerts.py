"""Daily goals progress + threshold alerts (RescueTime borrow)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from backend.behavior.category_scores import PRODUCTIVE_THRESHOLD, load_score_map
from backend.behavior.productivity_policy import load_policy_dict
from backend.behavior.stats_aggregate import aggregate_session_rows
from backend.models.timetable import TrackedSession
from backend.paths import ROOT

_STATE_PATH = ROOT / "data" / "behavior" / "goals_alert_state.json"

_YOUTUBE_MATCH = ("youtube.com", "youtu.be", "youtube")

DEFAULT_ALERTS: list[dict[str, Any]] = [
    {
        "id": "youtube_cap_30m",
        "kind": "site_cap",
        "label": "YouTube 30 min",
        "match": _YOUTUBE_MATCH,
        "max_seconds": 1800,
    },
]


def _read_state() -> dict[str, Any]:
    try:
        if _STATE_PATH.is_file():
            raw = json.loads(_STATE_PATH.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                return raw
    except Exception:
        pass
    return {}


def _write_state(data: dict[str, Any]) -> None:
    try:
        _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _STATE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass


def was_fired(day: date, alert_id: str) -> bool:
    day_key = day.isoformat()
    state = _read_state()
    fired = state.get(day_key)
    if not isinstance(fired, dict):
        return False
    return bool(fired.get(alert_id))


def mark_fired(day: date, alert_id: str) -> None:
    day_key = day.isoformat()
    state = _read_state()
    fired = state.get(day_key)
    if not isinstance(fired, dict):
        fired = {}
    fired[alert_id] = True
    state[day_key] = fired
    # Keep last 14 days
    keys = sorted(state.keys())[-14:]
    state = {k: state[k] for k in keys}
    _write_state(state)


def _site_matches(label: str, match: tuple[str, ...]) -> bool:
    low = (label or "").lower()
    return any(m in low for m in match)


def _aggregate_totals(
    db: Session,
    user_ids: list[int],
    day: date,
    *,
    user_id: int,
) -> dict[str, Any]:
    from backend.planner.service import local_day_bounds_utc

    from backend.behavior.session_merge import merge_tracked_rows

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

    productive = 0
    site_seconds: dict[str, int] = {}

    for _exe, bucket in buckets.items():
        if bucket.sites:
            for site_label, site in bucket.sites.items():
                site_seconds[site_label] = site_seconds.get(site_label, 0) + site.seconds
                if site.productivity_score >= PRODUCTIVE_THRESHOLD:
                    productive += site.seconds
        else:
            if bucket.productivity_score >= PRODUCTIVE_THRESHOLD:
                productive += bucket.seconds

    return {
        "total_seconds": total,
        "productive_seconds": productive,
        "site_seconds": site_seconds,
        "daily_goal_seconds": int(policy.get("daily_goal_minutes") or 240) * 60,
    }


def build_goals_status(
    db: Session,
    user_ids: list[int],
    day: date,
    *,
    user_id: int,
) -> dict[str, Any]:
    """Status payload for API — goals + alerts without firing."""
    totals = _aggregate_totals(db, user_ids, day, user_id=user_id)
    goal_target = totals["daily_goal_seconds"]
    productive = totals["productive_seconds"]
    goal_pct = round(100 * productive / goal_target) if goal_target else 0

    goals = [
        {
            "id": "productive_daily_goal",
            "label": "Daily productive time",
            "current_seconds": productive,
            "target_seconds": goal_target,
            "pct": min(100, goal_pct),
            "met": productive >= goal_target,
            "fired": was_fired(day, "productive_daily_goal"),
        }
    ]

    alerts: list[dict[str, Any]] = []
    for spec in DEFAULT_ALERTS:
        if spec["kind"] == "site_cap":
            match = spec.get("match") or ()
            current = sum(
                secs
                for label, secs in totals["site_seconds"].items()
                if _site_matches(label, match)
            )
            max_s = int(spec.get("max_seconds") or 0)
            alerts.append({
                "id": spec["id"],
                "label": spec.get("label") or spec["id"],
                "kind": spec["kind"],
                "current_seconds": current,
                "max_seconds": max_s,
                "triggered": current >= max_s > 0,
                "fired": was_fired(day, spec["id"]),
            })

    return {
        "date": day.isoformat(),
        "goals": goals,
        "alerts": alerts,
        "productive_seconds": productive,
        "total_seconds": totals["total_seconds"],
    }


def evaluate_and_fire(
    db: Session,
    user_ids: list[int],
    day: date,
    *,
    user_id: int,
) -> list[dict[str, Any]]:
    """Check thresholds; enqueue alerts once per day. Returns fired events."""
    from backend.behavior.gate_alerts import enqueue_alert

    status = build_goals_status(db, user_ids, day, user_id=user_id)
    fired: list[dict[str, Any]] = []

    for goal in status["goals"]:
        gid = goal["id"]
        if goal["met"] and not was_fired(day, gid):
            mark_fired(day, gid)
            mins = round(goal["target_seconds"] / 60)
            msg = f"Daily focus goal reached — {mins} productive minutes logged."
            enqueue_alert("goal_met", detail=gid, message=msg)
            fired.append({"id": gid, "kind": "goal", "message": msg})

    for alert in status["alerts"]:
        aid = alert["id"]
        if alert["triggered"] and not was_fired(day, aid):
            mark_fired(day, aid)
            mins = round(alert["max_seconds"] / 60)
            msg = f"Alert: {alert['label']} — over {mins} minutes today."
            enqueue_alert("threshold_alert", detail=aid, message=msg)
            try:
                from backend.behavior.study_mode_nudge import arm_study_mode_nudge

                arm_study_mode_nudge(reason=aid)
            except Exception:
                pass
            fired.append({"id": aid, "kind": "alert", "message": msg})

    return fired
