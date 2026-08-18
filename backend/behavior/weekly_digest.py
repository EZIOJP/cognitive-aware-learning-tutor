"""Weekly productivity digest aggregation."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy.orm import Session

from backend.behavior.goals_alerts import build_goals_status
from backend.behavior.productivity_pulse import attach_pulse
from backend.behavior.stats_aggregate import aggregate_session_rows, desktop_sessions_payload
from backend.models.timetable import TrackedSession
from backend.planner.service import local_day_bounds_utc


def _top_drains(sessions: list[dict[str, Any]], *, limit: int = 3) -> list[dict[str, Any]]:
    drains: list[tuple[str, int, int]] = []
    for s in sessions:
        score = int(s.get("productivity_score") or 35)
        if score >= 40:
            continue
        secs = int(s.get("seconds") or 0)
        if secs <= 0:
            continue
        if s.get("kind") == "browser" and s.get("sites"):
            for site in s["sites"]:
                sc = int(site.get("productivity_score") or 35)
                if sc >= 40:
                    continue
                ss = int(site.get("seconds") or 0)
                if ss > 0:
                    drains.append((str(site.get("site") or "site"), ss, sc))
        else:
            label = str(s.get("exe") or "app")
            drains.append((label, secs, score))
    merged: dict[str, dict[str, Any]] = {}
    for label, secs, score in drains:
        row = merged.setdefault(label, {"label": label, "seconds": 0, "productivity_score": score})
        row["seconds"] += secs
    ranked = sorted(merged.values(), key=lambda x: x["seconds"], reverse=True)
    return ranked[:limit]


def build_weekly_digest(
    db: Session,
    user_ids: list[int],
    *,
    user_id: int,
    end_day: date | None = None,
    days: int = 7,
) -> dict[str, Any]:
    from backend.behavior.category_scores import load_score_map
    from backend.behavior.productivity_policy import load_policy_dict
    from backend.behavior.session_merge import merge_tracked_rows

    end = end_day or date.today()
    start = end - timedelta(days=max(1, days) - 1)
    scores = load_score_map(db)
    policy = load_policy_dict(db, user_id)

    day_rows: list[dict[str, Any]] = []
    pulse_sum = 0
    pulse_count = 0
    adherence_hits = 0
    all_drains: dict[str, int] = {}

    d = start
    while d <= end:
        bounds_start, bounds_end = local_day_bounds_utc(d)
        rows = (
            db.query(TrackedSession)
            .filter(
                TrackedSession.user_id.in_(user_ids),
                TrackedSession.source.in_(("desktop_tracker", "extension", "calt_spa")),
                TrackedSession.start_time >= bounds_start,
                TrackedSession.start_time < bounds_end,
            )
            .all()
        )
        rows = merge_tracked_rows(rows)
        buckets, total = aggregate_session_rows(rows, scores=scores, policy=policy)
        sessions = desktop_sessions_payload(buckets, limit=50)
        payload = attach_pulse({
            "sessions": sessions,
            "total_seconds": total,
            "date": d.isoformat(),
        })
        goals = build_goals_status(db, user_ids, d, user_id=user_id)
        productive = int(goals.get("productive_seconds") or 0)
        target = int(goals["goals"][0]["target_seconds"]) if goals.get("goals") else 0
        met = bool(goals["goals"][0]["met"]) if goals.get("goals") else False
        if met:
            adherence_hits += 1
        pulse = int(payload.get("pulse") or 0)
        if total > 0:
            pulse_sum += pulse
            pulse_count += 1
        for drain in _top_drains(sessions, limit=10):
            all_drains[drain["label"]] = all_drains.get(drain["label"], 0) + drain["seconds"]
        day_rows.append({
            "date": d.isoformat(),
            "pulse": pulse,
            "total_seconds": total,
            "productive_seconds": productive,
            "goal_met": met,
            "goal_pct": goals["goals"][0]["pct"] if goals.get("goals") else 0,
        })
        d += timedelta(days=1)

    top_drains = [
        {"label": k, "seconds": v}
        for k, v in sorted(all_drains.items(), key=lambda x: x[1], reverse=True)[:3]
    ]

    return {
        "from": start.isoformat(),
        "to": end.isoformat(),
        "days": day_rows,
        "avg_pulse": round(pulse_sum / pulse_count) if pulse_count else 0,
        "goal_met_days": adherence_hits,
        "tracked_days": pulse_count,
        "top_drains": top_drains,
    }
