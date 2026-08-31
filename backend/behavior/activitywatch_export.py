"""ActivityWatch-compatible event export from tracked sessions."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from backend.models.timetable import TrackedSession
from backend.planner.service import iso_utc, local_day_bounds_utc


def export_activitywatch_events(
    db: Session,
    user_ids: list[int],
    day: date,
) -> list[dict[str, Any]]:
    """Return AW-style window events for one calendar day."""
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
    events: list[dict[str, Any]] = []
    for row in rows:
        if not row.start_time or not row.end_time:
            continue
        st = row.start_time.astimezone(timezone.utc)
        en = row.end_time.astimezone(timezone.utc)
        dur = max(0.0, (en - st).total_seconds())
        if dur <= 0:
            continue
        app = (row.app_name or "unknown").strip()
        site = (row.window_title or "").strip()
        if site and ("." in site or site.startswith("http")):
            data: dict[str, Any] = {"app": app, "title": site}
            if "." in site and not site.startswith("http"):
                data["url"] = f"https://{site.split()[0]}"
        else:
            data = {"app": app}
            if row.window_title:
                data["title"] = row.window_title
        events.append({
            "id": f"calt-{row.session_id}",
            "timestamp": iso_utc(st),
            "duration": dur,
            "data": data,
        })
    return events


def export_activitywatch_payload(
    db: Session,
    user_ids: list[int],
    day: date,
) -> dict[str, Any]:
    events = export_activitywatch_events(db, user_ids, day)
    return {
        "ok": True,
        "format": "activitywatch/events/v1",
        "day": day.isoformat(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "event_count": len(events),
        "events": events,
    }
