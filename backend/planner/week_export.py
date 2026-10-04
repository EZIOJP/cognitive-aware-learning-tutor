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
from backend.planner.service import _utc, iso_utc, local_day_bounds_utc, serialize_block
from backend.timetable.tracker_query import tracker_user_ids

_WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

# Cap at 366 calendar days (~1 leap year). Longer windows are rarely useful
# for timetable drafting and can stress SQLite session scans.
MAX_EXPORT_DAYS = 366


def _local_hour(dt: datetime) -> int:
    return _utc(dt).astimezone().hour


def is_empty_export_day(day: dict[str, Any]) -> bool:
    """Return True when a day has no tracked, planned, or wearable signal.

    Empty means all of:
    - no tracker sessions / zero actual & productive minutes
    - no planner blocks (planned_minutes and block_count both zero)
    - no wearable snapshot attached
    """
    if int(day.get("session_count") or 0) > 0:
        return False
    if float(day.get("actual_minutes") or 0) > 0:
        return False
    if float(day.get("productive_minutes") or 0) > 0:
        return False
    if float(day.get("planned_minutes") or 0) > 0:
        return False
    if int(day.get("block_count") or 0) > 0:
        return False
    if day.get("wearable") is not None:
        return False
    return True


def omit_empty_export_days(by_day: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop blank calendar days from export rows (CSV/JSON by_day series)."""
    return [day for day in by_day if not is_empty_export_day(day)]


def _clamp_presence_window(start: date, end: date) -> tuple[date, date]:
    """Normalize and cap an inclusive [start, end] to MAX_EXPORT_DAYS."""
    if end < start:
        start, end = end, start
    if (end - start).days + 1 > MAX_EXPORT_DAYS:
        start = end - timedelta(days=MAX_EXPORT_DAYS - 1)
    return start, end


def _mark_local_days_in_span(
    marked: set[date],
    span_start: datetime,
    span_end: datetime,
    window_start: date,
    window_end: date,
    *,
    min_seconds: float = 0.0,
) -> None:
    """Mark host-local calendar days that overlap [span_start, span_end]."""
    if span_end <= span_start:
        return
    local_start = _utc(span_start).astimezone()
    local_end = _utc(span_end).astimezone()
    day = max(local_start.date(), window_start)
    last = min(local_end.date(), window_end)
    while day <= last:
        day_start, day_end = local_day_bounds_utc(day)
        seg_start = max(_utc(span_start), day_start)
        seg_end = min(_utc(span_end), day_end)
        if (seg_end - seg_start).total_seconds() >= min_seconds:
            marked.add(day)
        day += timedelta(days=1)


def list_nonempty_export_days(
    db: Session,
    user: User,
    *,
    start: date,
    end: date,
) -> list[str]:
    """Return ISO dates in inclusive [start, end] with export-worthy signal.

    Matches ``is_empty_export_day`` intent without building full day metrics:
    wearable snapshot, planner blocks, or non-ignored tracker sessions (≥2s).
    """
    start, end = _clamp_presence_window(start, end)
    marked: set[date] = set()
    user_ids = tracker_user_ids(db, user)
    range_start, _ = local_day_bounds_utc(start)
    _, range_end = local_day_bounds_utc(end)

    for (local_date,) in (
        db.query(WearableDaily.local_date)
        .filter(
            WearableDaily.user_id == user.id,
            WearableDaily.local_date >= start,
            WearableDaily.local_date <= end,
        )
        .all()
    ):
        marked.add(local_date)

    blocks = (
        db.query(PlannerBlock.start_at, PlannerBlock.end_at)
        .filter(
            PlannerBlock.user_id == user.id,
            PlannerBlock.start_at < range_end,
            PlannerBlock.end_at > range_start,
            PlannerBlock.status.in_(("scheduled", "in_progress", "done")),
        )
        .all()
    )
    for start_at, end_at in blocks:
        if start_at is None or end_at is None:
            continue
        _mark_local_days_in_span(marked, start_at, end_at, start, end)

    sessions = (
        db.query(
            TrackedSession.start_time,
            TrackedSession.end_time,
            TrackedSession.app_name,
            TrackedSession.window_title,
            TrackedSession.source,
        )
        .filter(
            TrackedSession.user_id.in_(user_ids),
            TrackedSession.source.in_(("desktop_tracker", "extension", "calt_spa")),
            TrackedSession.start_time < range_end,
            TrackedSession.end_time > range_start,
        )
        .all()
    )
    for start_time, end_time, app_name, window_title, source in sessions:
        if start_time is None or end_time is None:
            continue
        if is_ignored_app(app_name or "", window_title or "", source=source):
            continue
        _mark_local_days_in_span(
            marked,
            start_time,
            end_time,
            start,
            end,
            min_seconds=2.0,
        )

    return [d.isoformat() for d in sorted(marked)]


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
    skip_empty: bool = True,
) -> dict[str, Any]:
    """Aggregate plan vs actual for the last `days` calendar days (inclusive of end_day).

    When ``skip_empty`` is True (default), ``by_day`` omits days with no tracked
    sessions, no planner blocks, and no wearable snapshot. Summary / weekday
    patterns still cover the full requested window.
    """
    days = max(1, min(int(days), MAX_EXPORT_DAYS))
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
        and not is_ignored_app(s.app_name or "", s.window_title or "", source=s.source)
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
    session_rows: list[dict[str, Any]] = []
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
            hour = _local_hour(seg_start)
            hour_minutes[hour] += mins
            score = int(score_fn(s))
            session_rows.append(
                {
                    "session_id": s.session_id,
                    "date": day.isoformat(),
                    "weekday": weekday,
                    "start_at": iso_utc(seg_start),
                    "end_at": iso_utc(seg_end),
                    "minutes": round(mins, 2),
                    "hour": hour,
                    "app_name": app,
                    "window_title": (s.window_title or "")[:240],
                    "category": cat,
                    "source": s.source or "",
                    "category_source": s.category_source or "",
                    "productivity_score": score,
                    "is_productive": bool(score >= threshold),
                    "override_productive": s.override_productive,
                }
            )

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

    exported_days = omit_empty_export_days(by_day) if skip_empty else by_day
    empty_omitted = max(0, len(by_day) - len(exported_days))
    exported_dates = {d["date"] for d in exported_days}
    exported_sessions = [r for r in session_rows if r["date"] in exported_dates]
    tables = build_tidy_export_tables(
        exported_days,
        sessions=exported_sessions,
        weekday_patterns=weekday_patterns,
        hints=hints,
    )

    return {
        "export_version": "1.4",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "purpose": (
            "Last-N-days productivity for analysis and timetable design. "
            "Use `tables` (tidy long format) for pandas/R; `by_day` stays nested "
            "for apps that prefer day objects."
        ),
        "range": {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "days": days,
            "days_exported": len(exported_days),
            "empty_days_omitted": empty_omitted,
            "skip_empty": bool(skip_empty),
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
            "session_rows": len(exported_sessions),
        },
        "weekday_patterns": weekday_patterns,
        "suggested_timetable_hints": hints,
        "by_day": exported_days,
        "tables": tables,
    }


def build_tidy_export_tables(
    by_day: list[dict[str, Any]],
    *,
    sessions: list[dict[str, Any]] | None = None,
    weekday_patterns: dict[str, Any] | None = None,
    hints: list[str] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Build tidy long-format frames for analysis (pandas / R / Sheets)."""
    day_metrics: list[dict[str, Any]] = []
    day_hour: list[dict[str, Any]] = []
    day_category: list[dict[str, Any]] = []
    day_app: list[dict[str, Any]] = []
    planned_blocks: list[dict[str, Any]] = []
    wearable_daily: list[dict[str, Any]] = []

    for day in by_day:
        date_s = day.get("date")
        weekday = day.get("weekday")
        day_metrics.append(
            {
                "date": date_s,
                "weekday": weekday,
                "planned_minutes": day.get("planned_minutes"),
                "actual_minutes": day.get("actual_minutes"),
                "productive_minutes": day.get("productive_minutes"),
                "effective_focus_minutes": day.get("effective_focus_minutes"),
                "on_plan_focus_minutes": day.get("on_plan_focus_minutes"),
                "off_plan_productive_minutes": day.get("off_plan_productive_minutes"),
                "distraction_on_plan_minutes": day.get("distraction_on_plan_minutes"),
                "adherence_pct": day.get("adherence_pct"),
                "block_count": day.get("block_count"),
                "session_count": day.get("session_count"),
            }
        )
        hours = day.get("by_hour_minutes") or {}
        for h in range(24):
            day_hour.append(
                {
                    "date": date_s,
                    "weekday": weekday,
                    "hour": h,
                    "minutes": float(hours.get(str(h), 0) or 0),
                }
            )
        for cat, mins in (day.get("by_category_minutes") or {}).items():
            day_category.append(
                {
                    "date": date_s,
                    "weekday": weekday,
                    "category": cat,
                    "minutes": mins,
                }
            )
        for app_row in day.get("top_apps") or []:
            day_app.append(
                {
                    "date": date_s,
                    "weekday": weekday,
                    "app": app_row.get("app"),
                    "minutes": app_row.get("minutes"),
                }
            )
        for block in day.get("planned_blocks") or []:
            planned_blocks.append(
                {
                    "date": date_s,
                    "weekday": weekday,
                    "block_id": block.get("id"),
                    "title": block.get("title"),
                    "category": block.get("category"),
                    "start_at": block.get("start_at"),
                    "end_at": block.get("end_at"),
                    "planned_minutes": block.get("planned_minutes"),
                    "remaining_minutes": block.get("remaining_minutes"),
                    "status": block.get("status"),
                    "task_id": block.get("task_id"),
                    "rolled_from_id": block.get("rolled_from_id"),
                    "roll_count": block.get("roll_count"),
                }
            )
        wearable = day.get("wearable")
        if wearable:
            wearable_daily.append(
                {
                    "date": date_s,
                    "weekday": weekday,
                    "source": wearable.get("source"),
                    "sleep_hours": wearable.get("sleep_hours"),
                    "sleep_score": wearable.get("sleep_score"),
                    "sleep_deep_minutes": wearable.get("sleep_deep_minutes"),
                    "steps": wearable.get("steps"),
                    "step_target": wearable.get("step_target"),
                    "calories": wearable.get("calories"),
                    "calorie_target": wearable.get("calorie_target"),
                    "distance_meters": wearable.get("distance_meters"),
                    "heart_rate_last": wearable.get("heart_rate_last"),
                    "heart_rate_resting": wearable.get("heart_rate_resting"),
                    "spo2_pct": wearable.get("spo2_pct"),
                    "stress": wearable.get("stress"),
                    "pai_today": wearable.get("pai_today"),
                    "pai_total": wearable.get("pai_total"),
                    "stand_hours": wearable.get("stand_hours"),
                    "stand_target": wearable.get("stand_target"),
                    "battery_pct": wearable.get("battery_pct"),
                    "captured_at": wearable.get("captured_at"),
                    "synced_at": wearable.get("synced_at"),
                }
            )

    weekday_hour: list[dict[str, Any]] = []
    for wd in _WEEKDAYS:
        pattern = (weekday_patterns or {}).get(wd) or {}
        avg_hours = pattern.get("avg_hour_minutes") or [0.0] * 24
        for h, mins in enumerate(avg_hours):
            weekday_hour.append(
                {
                    "weekday": wd,
                    "hour": h,
                    "avg_minutes": mins,
                    "days_sampled": pattern.get("days_sampled", 0),
                }
            )

    return {
        "day_metrics": day_metrics,
        "day_hour": day_hour,
        "day_category": day_category,
        "day_app": day_app,
        "sessions": list(sessions or []),
        "planned_blocks": planned_blocks,
        "wearable_daily": wearable_daily,
        "weekday_hour": weekday_hour,
        "hints": [{"hint": h} for h in (hints or [])],
    }


def filter_export_payload(
    payload: dict[str, Any],
    *,
    include: set[str] | None = None,
    productive_only: bool = False,
) -> dict[str, Any]:
    """Slim export for custom download / LLM propose."""
    include = include or {
        "summary",
        "patterns",
        "by_day",
        "blocks",
        "hints",
        "policy",
        "wearable",
        "tables",
        "sessions",
    }
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

    want_tables = bool({"tables", "sessions", "by_day", "blocks", "wearable"} & include)
    if want_tables:
        tables = dict(payload.get("tables") or {})
        if not tables and out.get("by_day") is not None:
            tables = build_tidy_export_tables(
                out.get("by_day") or [],
                sessions=(payload.get("tables") or {}).get("sessions") or [],
                weekday_patterns=payload.get("weekday_patterns")
                if "patterns" in include
                else {},
                hints=payload.get("suggested_timetable_hints")
                if "hints" in include
                else [],
            )
        if "sessions" not in include and "tables" not in include:
            tables.pop("sessions", None)
        if "blocks" not in include and "tables" not in include:
            tables.pop("planned_blocks", None)
        if "wearable" not in include and "tables" not in include:
            tables.pop("wearable_daily", None)
        if "patterns" not in include and "tables" not in include:
            tables.pop("weekday_hour", None)
        if "hints" not in include and "tables" not in include:
            tables.pop("hints", None)
        if productive_only and tables.get("sessions"):
            tables["sessions"] = [
                r for r in tables["sessions"] if r.get("is_productive")
            ]
        out["tables"] = tables
    return out


_TABLE_ORDER = (
    "day_metrics",
    "day_hour",
    "day_category",
    "day_app",
    "sessions",
    "planned_blocks",
    "wearable_daily",
    "weekday_hour",
    "hints",
)


def _write_table_section(
    writer: Any,
    name: str,
    rows: list[dict[str, Any]],
    columns: list[str],
) -> None:
    writer.writerow([])
    writer.writerow([f"# table:{name}"])
    writer.writerow(columns)
    for row in rows:
        writer.writerow([row.get(col, "") if row.get(col) is not None else "" for col in columns])


def export_as_csv(payload: dict[str, Any]) -> str:
    """Tidy multi-table CSV (long format) for analysis tools.

    Sections are marked ``# table:<name>`` then a header row. Load in pandas with
    a small section splitter, or open in Sheets and split on those markers.
    """
    tables = payload.get("tables")
    if not isinstance(tables, dict) or not tables:
        tables = build_tidy_export_tables(
            payload.get("by_day") or [],
            weekday_patterns=payload.get("weekday_patterns"),
            hints=payload.get("suggested_timetable_hints") or [],
        )

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["# CALT productivity export - tidy long format"])
    writer.writerow(
        [
            f"# version={payload.get('export_version', '')}",
            f"exported_at={payload.get('exported_at', '')}",
            f"range_start={(payload.get('range') or {}).get('start', '')}",
            f"range_end={(payload.get('range') or {}).get('end', '')}",
        ]
    )

    schemas: dict[str, list[str]] = {
        "day_metrics": [
            "date",
            "weekday",
            "planned_minutes",
            "actual_minutes",
            "productive_minutes",
            "effective_focus_minutes",
            "on_plan_focus_minutes",
            "off_plan_productive_minutes",
            "distraction_on_plan_minutes",
            "adherence_pct",
            "block_count",
            "session_count",
        ],
        "day_hour": ["date", "weekday", "hour", "minutes"],
        "day_category": ["date", "weekday", "category", "minutes"],
        "day_app": ["date", "weekday", "app", "minutes"],
        "sessions": [
            "session_id",
            "date",
            "weekday",
            "start_at",
            "end_at",
            "minutes",
            "hour",
            "app_name",
            "window_title",
            "category",
            "source",
            "category_source",
            "productivity_score",
            "is_productive",
            "override_productive",
        ],
        "planned_blocks": [
            "date",
            "weekday",
            "block_id",
            "title",
            "category",
            "start_at",
            "end_at",
            "planned_minutes",
            "remaining_minutes",
            "status",
            "task_id",
            "rolled_from_id",
            "roll_count",
        ],
        "wearable_daily": [
            "date",
            "weekday",
            "source",
            "sleep_hours",
            "sleep_score",
            "sleep_deep_minutes",
            "steps",
            "step_target",
            "calories",
            "calorie_target",
            "distance_meters",
            "heart_rate_last",
            "heart_rate_resting",
            "spo2_pct",
            "stress",
            "pai_today",
            "pai_total",
            "stand_hours",
            "stand_target",
            "battery_pct",
            "captured_at",
            "synced_at",
        ],
        "weekday_hour": ["weekday", "hour", "avg_minutes", "days_sampled"],
        "hints": ["hint"],
    }

    for name in _TABLE_ORDER:
        cols = schemas[name]
        rows = tables.get(name) or []
        if name == "hints" and not rows:
            rows = [{"hint": h} for h in (payload.get("suggested_timetable_hints") or [])]
        _write_table_section(writer, name, rows, cols)

    return buf.getvalue()


def export_as_csv_wide(payload: dict[str, Any]) -> str:
    """Legacy wide day × hour CSV (one row per day, h00–h23 columns)."""
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
    writer.writerow([])
    writer.writerow(["# hints"])
    for hint in payload.get("suggested_timetable_hints") or []:
        writer.writerow([hint])
    return buf.getvalue()
