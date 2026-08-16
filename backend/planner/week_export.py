"""Export last N days of planner + tracked productivity for timetable design."""

from __future__ import annotations

import csv
import io
import json
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from backend.behavior.category_scores import load_score_map
from backend.behavior.productivity_policy import load_policy_dict, resolve_session_score
from backend.behavior.tracker_ignore import is_ignored_app
from backend.models import User
from backend.models.planner import PlannerBlock
from backend.models.timetable import TrackedSession
from backend.models.wearable_daily import WearableDaily
from backend.planner.day_metrics import compute_day_metrics
from backend.planner.service import _utc, local_day_bounds_utc, serialize_block
from backend.timetable.tracker_query import tracker_user_ids

_WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def _local_hour(dt: datetime) -> int:
    return _utc(dt).astimezone().hour


def _wearable_export(row: WearableDaily | None) -> dict[str, Any] | None:
    """Serialize every normalized watch metric plus its original payload, if any."""
    if row is None:
        return None
    raw_payload: Any = None
    if row.payload_json:
        try:
            raw_payload = json.loads(row.payload_json)
        except (TypeError, ValueError):
            raw_payload = row.payload_json
    return {
        "source": row.source,
        "sleep_hours": row.sleep_hours,
        "sleep_score": row.sleep_score,
        "sleep_deep_minutes": row.sleep_deep_min,
        "steps": row.steps,
        "step_target": row.step_target,
        "calories": row.calories,
        "calorie_target": row.calorie_target,
        "distance_meters": row.distance_m,
        "heart_rate_last": row.hr_last,
        "heart_rate_resting": row.hr_resting,
        "spo2_pct": row.spo2,
        "stress": row.stress,
        "pai_today": row.pai_today,
        "pai_total": row.pai_total,
        "stand_hours": row.stand_hours,
        "stand_target": row.stand_target,
        "battery_pct": row.battery_pct,
        "captured_at": row.last_captured_at.isoformat() if row.last_captured_at else None,
        "synced_at": row.synced_at.isoformat() if row.synced_at else None,
        "raw_payload": raw_payload,
    }


def build_productivity_week_export(
    db: Session,
    user: User,
    *,
    days: int = 7,
    end_day: date | None = None,
) -> dict[str, Any]:
    """Aggregate plan vs actual for the last `days` calendar days (inclusive of end_day)."""
    days = max(1, min(int(days), 31))
    end = end_day or date.today()
    start = end - timedelta(days=days - 1)

    scores = load_score_map(db)
    policy = load_policy_dict(db, user.id)
    threshold = int(policy.get("threshold") or 60)

    def score_fn(sess):
        return resolve_session_score(sess, scores, policy)

    user_ids = tracker_user_ids(db, user)
    range_start, _ = local_day_bounds_utc(start)
    _, range_end = local_day_bounds_utc(end)

    all_blocks = (
        db.query(PlannerBlock)
        .filter(
            PlannerBlock.user_id == user.id,
            PlannerBlock.start_at < range_end,
            PlannerBlock.end_at > range_start,
            PlannerBlock.status.in_(("scheduled", "in_progress", "done")),
        )
        .order_by(PlannerBlock.start_at)
        .all()
    )

    all_sessions = (
        db.query(TrackedSession)
        .filter(
            TrackedSession.user_id.in_(user_ids),
            TrackedSession.source.in_(("desktop_tracker", "extension", "calt_spa")),
            TrackedSession.start_time < range_end,
            TrackedSession.end_time > range_start,
        )
        .order_by(TrackedSession.start_time)
        .all()
    )
    all_sessions = [
        s
        for s in all_sessions
        if s.start_time
        and s.end_time
        and not is_ignored_app(s.app_name or "", s.window_title or "")
    ]
    wearable_by_day = {
        row.local_date: row
        for row in db.query(WearableDaily)
        .filter(
            WearableDaily.user_id == user.id,
            WearableDaily.local_date >= start,
            WearableDaily.local_date <= end,
        )
        .all()
    }

    by_day: list[dict[str, Any]] = []
    weekday_hour_sum: dict[str, list[float]] = {k: [0.0] * 24 for k in _WEEKDAYS}
    weekday_day_count: dict[str, int] = defaultdict(int)
    weekday_productive: dict[str, list[float]] = defaultdict(list)
    global_cat_minutes: dict[str, float] = defaultdict(float)
    global_app_minutes: dict[str, float] = defaultdict(float)
    total_tracked_minutes = 0.0
    total_productive_minutes = 0.0

    for offset in range(days):
        day = start + timedelta(offset)
        day_start, day_end = local_day_bounds_utc(day)
        weekday = _WEEKDAYS[day.weekday()]

        day_blocks = [
            b
            for b in all_blocks
            if _utc(b.start_at) < day_end and _utc(b.end_at) > day_start
        ]
        day_sessions = [
            s
            for s in all_sessions
            if _utc(s.start_time) < day_end and _utc(s.end_time) > day_start
        ]

        hour_minutes = [0.0] * 24
        cat_minutes: dict[str, float] = defaultdict(float)
        app_minutes: dict[str, float] = defaultdict(float)

        for s in day_sessions:
            # Clip session to day bounds (normalize naive SQLite datetimes)
            seg_start = max(_utc(s.start_time), day_start)
            seg_end = min(_utc(s.end_time), day_end)
            secs = max(0.0, (seg_end - seg_start).total_seconds())
            if secs < 2:
                continue
            mins = secs / 60.0
            cat = (s.category or "uncategorized").strip() or "uncategorized"
            app = (s.app_name or "unknown").strip() or "unknown"
            cat_minutes[cat] += mins
            app_minutes[app] += mins
            global_cat_minutes[cat] += mins
            global_app_minutes[app] += mins
            # Attribute minutes to local hour of segment start (good enough for heatmaps)
            hour_minutes[_local_hour(seg_start)] += mins

        metrics = compute_day_metrics(
            day, day_blocks, day_sessions, score_fn, threshold=threshold
        )
        actual_minutes = float(metrics["actual_minutes"])
        productive_minutes = float(metrics["productive_minutes"])
        planned_minutes = metrics["planned_minutes"]
        effective_focus = metrics["effective_focus_minutes"]
        adherence_pct = metrics["adherence_pct"]

        top_apps = sorted(app_minutes.items(), key=lambda x: -x[1])[:8]
        top_cats = sorted(cat_minutes.items(), key=lambda x: -x[1])[:8]

        by_day.append(
            {
                "date": day.isoformat(),
                "weekday": weekday,
                "planned_minutes": planned_minutes,
                "actual_minutes": round(actual_minutes, 1),
                "productive_minutes": round(productive_minutes, 1),
                "effective_focus_minutes": effective_focus,
                "on_plan_focus_minutes": metrics["on_plan_focus_minutes"],
                "off_plan_productive_minutes": metrics["off_plan_productive_minutes"],
                "distraction_on_plan_minutes": metrics["distraction_on_plan_minutes"],
                "adherence_pct": adherence_pct,
                "block_count": metrics["block_count"],
                "session_count": metrics["session_count"],
                "planned_blocks": [serialize_block(b) for b in day_blocks],
                "by_category_minutes": {
                    k: round(v, 1) for k, v in sorted(cat_minutes.items(), key=lambda x: -x[1])
                },
                "by_hour_minutes": {str(h): round(hour_minutes[h], 1) for h in range(24)},
                "top_apps": [
                    {"app": a, "minutes": round(m, 1)} for a, m in top_apps
                ],
                "wearable": _wearable_export(wearable_by_day.get(day)),
            }
        )

        weekday_day_count[weekday] += 1
        weekday_productive[weekday].append(productive_minutes)
        for h in range(24):
            weekday_hour_sum[weekday][h] += hour_minutes[h]

        total_tracked_minutes += actual_minutes
        total_productive_minutes += productive_minutes

    weekday_patterns: dict[str, Any] = {}
    for wd in _WEEKDAYS:
        n = max(1, weekday_day_count.get(wd, 0))
        avg_hours = [round(weekday_hour_sum[wd][h] / n, 1) for h in range(24)]
        prod_list = weekday_productive.get(wd) or [0.0]
        weekday_patterns[wd] = {
            "days_sampled": weekday_day_count.get(wd, 0),
            "avg_productive_minutes": round(sum(prod_list) / len(prod_list), 1),
            "avg_hour_minutes": avg_hours,
            "peak_hours": sorted(range(24), key=lambda h: -avg_hours[h])[:3],
        }

    # Global peak hours across the window
    hour_totals = [0.0] * 24
    for day_row in by_day:
        for h, m in day_row["by_hour_minutes"].items():
            hour_totals[int(h)] += float(m)
    peak_hours = sorted(range(24), key=lambda h: -hour_totals[h])[:5]
    peak_hours = [h for h in peak_hours if hour_totals[h] >= 15]  # ignore tiny noise

    busiest = max(
        _WEEKDAYS,
        key=lambda wd: weekday_patterns[wd]["avg_productive_minutes"],
    )
    quietest = min(
        (wd for wd in _WEEKDAYS if weekday_patterns[wd]["days_sampled"] > 0),
        key=lambda wd: weekday_patterns[wd]["avg_productive_minutes"],
        default="sun",
    )

    top_categories = [
        {"category": c, "minutes": round(m, 1)}
        for c, m in sorted(global_cat_minutes.items(), key=lambda x: -x[1])[:10]
    ]
    top_apps = [
        {"app": a, "minutes": round(m, 1)}
        for a, m in sorted(global_app_minutes.items(), key=lambda x: -x[1])[:12]
    ]

    hints: list[str] = []
    if peak_hours:
        spans = ", ".join(f"{h:02d}:00" for h in sorted(peak_hours[:3]))
        hints.append(f"Protect deep-work blocks near historically busy hours: {spans}.")
    hints.append(
        f"Busiest weekday for productive time: {busiest.upper()}; quieter: {quietest.upper()}."
    )
    if top_categories:
        hints.append(
            f"Top category last {days} days: {top_categories[0]['category']} "
            f"({top_categories[0]['minutes']} min) — schedule similar slots if that matches goals."
        )
    planned_any = any(d["planned_minutes"] > 0 for d in by_day)
    if planned_any:
        avg_adh = [
            d["adherence_pct"]
            for d in by_day
            if d["adherence_pct"] is not None
        ]
        if avg_adh:
            hints.append(
                f"Average plan adherence: {round(sum(avg_adh) / len(avg_adh), 1)}% — "
                "shrink or move blocks on low-adherence weekdays."
            )
    else:
        hints.append(
            "No planner blocks in this window — use hour heatmaps to draft a first weekly timetable."
        )

    return {
        "export_version": "1.2",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "purpose": (
            "Last-N-days productivity and wearable snapshot for designing weekly "
            "timetables (weekday patterns, peak hours, plan vs actual, health context)."
        ),
        "range": {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "days": days,
        },
        "policy_snapshot": policy,
        "summary": {
            "total_tracked_hours": round(total_tracked_minutes / 60.0, 2),
            "total_productive_hours": round(total_productive_minutes / 60.0, 2),
            "avg_tracked_minutes_per_day": round(total_tracked_minutes / days, 1),
            "avg_productive_minutes_per_day": round(total_productive_minutes / days, 1),
            "busiest_weekday": busiest,
            "quietest_weekday": quietest,
            "peak_hours": peak_hours[:5],
            "top_categories": top_categories,
            "top_apps": top_apps,
            "threshold": threshold,
        },
        "weekday_patterns": weekday_patterns,
        "suggested_timetable_hints": hints,
        "by_day": by_day,
    }


def filter_export_payload(
    payload: dict[str, Any],
    *,
    include: set[str] | None = None,
    productive_only: bool = False,
) -> dict[str, Any]:
    """Slim export for custom download / LLM propose."""
    include = include or {"summary", "patterns", "by_day", "blocks", "hints", "policy", "wearable"}
    out: dict[str, Any] = {
        "export_version": payload.get("export_version"),
        "exported_at": payload.get("exported_at"),
        "purpose": payload.get("purpose"),
        "range": payload.get("range"),
    }
    if "policy" in include:
        out["policy_snapshot"] = payload.get("policy_snapshot")
    if "summary" in include:
        out["summary"] = payload.get("summary")
    if "patterns" in include:
        out["weekday_patterns"] = payload.get("weekday_patterns")
    if "hints" in include:
        out["suggested_timetable_hints"] = payload.get("suggested_timetable_hints")
    if "by_day" in include or "blocks" in include:
        days = []
        for day in payload.get("by_day") or []:
            row = dict(day)
            if "blocks" not in include:
                row.pop("planned_blocks", None)
            if "wearable" not in include:
                row.pop("wearable", None)
            if productive_only:
                # Keep day row but zero non-productive category breakdown noise
                row["actual_minutes"] = row.get("productive_minutes", 0)
            days.append(row)
        out["by_day"] = days
    return out


def export_as_csv(payload: dict[str, Any]) -> str:
    """Flat day × hour CSV for spreadsheet timetable drafting."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "date",
            "weekday",
            "planned_minutes",
            "actual_minutes",
            "productive_minutes",
            "effective_focus_minutes",
            "adherence_pct",
            "top_category",
            "top_app",
            "sleep_hours",
            "sleep_score",
            "steps",
            "step_target",
            "calories",
            "distance_meters",
            "heart_rate_resting",
            "spo2_pct",
            "stress",
            "pai_today",
            "stand_hours",
            "battery_pct",
            *[f"h{h:02d}" for h in range(24)],
        ]
    )
    for day in payload.get("by_day") or []:
        cats = day.get("by_category_minutes") or {}
        apps = day.get("top_apps") or []
        wearable = day.get("wearable") or {}
        top_cat = next(iter(cats.keys()), "")
        top_app = apps[0]["app"] if apps else ""
        hours = day.get("by_hour_minutes") or {}
        writer.writerow(
            [
                day.get("date"),
                day.get("weekday"),
                day.get("planned_minutes"),
                day.get("actual_minutes"),
                day.get("productive_minutes"),
                day.get("effective_focus_minutes"),
                day.get("adherence_pct") if day.get("adherence_pct") is not None else "",
                top_cat,
                top_app,
                wearable.get("sleep_hours", ""),
                wearable.get("sleep_score", ""),
                wearable.get("steps", ""),
                wearable.get("step_target", ""),
                wearable.get("calories", ""),
                wearable.get("distance_meters", ""),
                wearable.get("heart_rate_resting", ""),
                wearable.get("spo2_pct", ""),
                wearable.get("stress", ""),
                wearable.get("pai_today", ""),
                wearable.get("stand_hours", ""),
                wearable.get("battery_pct", ""),
                *[hours.get(str(h), 0) for h in range(24)],
            ]
        )
    # Trailing summary section
    writer.writerow([])
    writer.writerow(["# hints"])
    for hint in payload.get("suggested_timetable_hints") or []:
        writer.writerow([hint])
    return buf.getvalue()
