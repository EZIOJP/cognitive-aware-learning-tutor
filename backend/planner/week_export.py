"""Export last N days of planner + tracked productivity for timetable design."""

from __future__ import annotations

import csv
import io
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from backend.behavior.category_scores import PRODUCTIVE_THRESHOLD, load_score_map, score_for_category
from backend.behavior.tracker_ignore import is_ignored_app
from backend.models import User
from backend.models.planner import PlannerBlock
from backend.models.timetable import TrackedSession
from backend.planner.effective_focus import effective_focus_minutes
from backend.planner.service import serialize_block
from backend.timetable.tracker_query import tracker_user_ids

_WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def _day_bounds_utc(day: date) -> tuple[datetime, datetime]:
    start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
    return start, start + timedelta(days=1)


def _local_hour(dt: datetime) -> int:
    return dt.astimezone().hour


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
    user_ids = tracker_user_ids(db, user)
    range_start, _ = _day_bounds_utc(start)
    _, range_end = _day_bounds_utc(end)

    all_blocks = (
        db.query(PlannerBlock)
        .filter(
            PlannerBlock.user_id == user.id,
            PlannerBlock.start_at < range_end,
            PlannerBlock.end_at > range_start,
            PlannerBlock.status.in_(("scheduled", "in_progress", "done", "rolled")),
        )
        .order_by(PlannerBlock.start_at)
        .all()
    )

    all_sessions = (
        db.query(TrackedSession)
        .filter(
            TrackedSession.user_id.in_(user_ids),
            TrackedSession.source == "desktop_tracker",
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
        day_start, day_end = _day_bounds_utc(day)
        weekday = _WEEKDAYS[day.weekday()]

        day_blocks = [
            b
            for b in all_blocks
            if b.start_at < day_end and b.end_at > day_start
        ]
        day_sessions = [
            s
            for s in all_sessions
            if s.start_time < day_end and s.end_time > day_start
        ]

        hour_minutes = [0.0] * 24
        cat_minutes: dict[str, float] = defaultdict(float)
        app_minutes: dict[str, float] = defaultdict(float)
        actual_minutes = 0.0
        productive_minutes = 0.0

        for s in day_sessions:
            # Clip session to day bounds
            seg_start = max(s.start_time, day_start)
            seg_end = min(s.end_time, day_end)
            secs = max(0.0, (seg_end - seg_start).total_seconds())
            if secs < 2:
                continue
            mins = secs / 60.0
            actual_minutes += mins
            cat = (s.category or "uncategorized").strip() or "uncategorized"
            app = (s.app_name or "unknown").strip() or "unknown"
            cat_minutes[cat] += mins
            app_minutes[app] += mins
            global_cat_minutes[cat] += mins
            global_app_minutes[app] += mins
            score = score_for_category(s.category, scores)
            if score >= PRODUCTIVE_THRESHOLD:
                productive_minutes += mins

            # Attribute minutes to local hour of segment start (good enough for heatmaps)
            hour_minutes[_local_hour(seg_start)] += mins

        planned_minutes = sum(b.planned_minutes for b in day_blocks)
        effective_focus = effective_focus_minutes(
            day_blocks,
            day_sessions,
            lambda cat: score_for_category(cat, scores),
        )
        adherence_pct = (
            round(100 * actual_minutes / planned_minutes, 1) if planned_minutes else None
        )

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
                "adherence_pct": adherence_pct,
                "block_count": len(day_blocks),
                "session_count": len(day_sessions),
                "planned_blocks": [serialize_block(b) for b in day_blocks],
                "by_category_minutes": {
                    k: round(v, 1) for k, v in sorted(cat_minutes.items(), key=lambda x: -x[1])
                },
                "by_hour_minutes": {str(h): round(hour_minutes[h], 1) for h in range(24)},
                "top_apps": [
                    {"app": a, "minutes": round(m, 1)} for a, m in top_apps
                ],
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
        "export_version": "1.0",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "purpose": (
            "Last-N-days productivity snapshot for designing weekly timetables "
            "(weekday patterns, peak hours, plan vs actual)."
        ),
        "range": {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "days": days,
        },
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
        },
        "weekday_patterns": weekday_patterns,
        "suggested_timetable_hints": hints,
        "by_day": by_day,
    }


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
            *[f"h{h:02d}" for h in range(24)],
        ]
    )
    for day in payload.get("by_day") or []:
        cats = day.get("by_category_minutes") or {}
        apps = day.get("top_apps") or []
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
                *[hours.get(str(h), 0) for h in range(24)],
            ]
        )
    # Trailing summary section
    writer.writerow([])
    writer.writerow(["# hints"])
    for hint in payload.get("suggested_timetable_hints") or []:
        writer.writerow([hint])
    return buf.getvalue()
