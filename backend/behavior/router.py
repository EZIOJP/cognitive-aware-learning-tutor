"""Browser behavior WebSocket + stats — hub readings (DB) with optional CSV mirror."""

from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from backend.core.auth import decode_user, ensure_demo_user, get_current_user
from backend.db.base import SessionLocal
from backend.db.session import get_db
from backend.hub.services.ingest import insert_reading
from backend.models import Reading, ReadingDefinition, User
from backend.paths import DATA_LOGS_DIR

router = APIRouter(tags=["behavior"])

LOG_DIR = DATA_LOGS_DIR
LOG_DIR.mkdir(exist_ok=True)


def _user_from_ws(websocket: WebSocket, db: Session) -> User:
    token = websocket.query_params.get("token")
    if not token:
        qs = parse_qs(websocket.scope.get("query_string", b"").decode())
        token = (qs.get("token") or [None])[0]
    if token:
        user = decode_user(token, db)
        if user:
            return user
    return ensure_demo_user(db)


def _append_csv(row: dict, day_str: str) -> None:
    csv_path = LOG_DIR / f"DSC_browser_behavior_{day_str}.csv"
    write_header = not csv_path.exists()
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        if write_header:
            writer.writeheader()
        writer.writerow(row)


@router.websocket("/ws/behavior")
async def behavior_websocket(websocket: WebSocket):
    await websocket.accept()
    today_str = datetime.now(UTC).strftime("%Y-%m-%d")

    try:
        while True:
            data = await websocket.receive_json()
            enriched = {**data, "received_at": datetime.now(UTC).isoformat()}
            _append_csv(enriched, today_str)

            db = SessionLocal()
            try:
                user = _user_from_ws(websocket, db)
                insert_reading(
                    db,
                    user_id=user.id,
                    slug="browser_event",
                    value_json=enriched,
                    source_device="extension",
                    client_event_id=enriched.get("event_id") or enriched.get("received_at"),
                )
            except (ValueError, Exception):
                pass
            finally:
                db.close()

            await websocket.send_json({"status": "ok"})
    except WebSocketDisconnect:
        pass


def _stats_from_db(db: Session, user_id: int, day: date) -> dict:
    defn = db.query(ReadingDefinition).filter(ReadingDefinition.slug == "browser_event").first()
    if not defn:
        return {"events_today": 0, "domains": [], "source": "database"}

    start = datetime.combine(day, datetime.min.time()).replace(tzinfo=UTC)
    end = start + timedelta(days=1)
    rows = (
        db.query(Reading)
        .filter(
            Reading.user_id == user_id,
            Reading.definition_id == defn.id,
            Reading.recorded_at >= start,
            Reading.recorded_at < end,
        )
        .all()
    )

    domains: Counter[str] = Counter()
    categories: Counter[str] = Counter()
    for row in rows:
        payload = json.loads(row.value_json) if row.value_json else {}
        domain = (
            payload.get("domain")
            or (payload.get("url") or "unknown")[:48]
            or "unknown"
        )
        domains[domain] += 1
        cat = payload.get("category") or payload.get("activity_type") or "other"
        categories[str(cat)] += 1

    top_domains = [{"domain": d, "count": c} for d, c in domains.most_common(10)]
    top_categories = [{"category": k, "count": v} for k, v in categories.most_common(8)]
    return {
        "events_today": len(rows),
        "domains": top_domains,
        "categories": top_categories,
        "source": "database",
        "date": day.isoformat(),
    }


def _stats_from_csv(day_str: str) -> dict | None:
    csv_path = LOG_DIR / f"DSC_browser_behavior_{day_str}.csv"
    if not csv_path.exists():
        return None
    rows: list[dict] = []
    with open(csv_path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    domains: Counter[str] = Counter()
    for row in rows:
        domain = row.get("domain") or (row.get("url") or "unknown")[:48]
        domains[domain] += 1
    top = [{"domain": d, "count": c} for d, c in domains.most_common(10)]
    return {
        "events_today": len(rows),
        "domains": top,
        "categories": [],
        "source": "csv_fallback",
        "date": day_str,
    }


def _shape_stats_for_ui(raw: dict) -> dict:
    """Normalize DB/CSV stats for dashboard widget."""
    events = raw.get("events_today", 0)
    domains = raw.get("domains") or []
    categories = raw.get("categories") or []
    top_domains = []
    for item in domains[:8]:
        if "seconds" in item:
            top_domains.append({"domain": item["domain"], "seconds": int(item["seconds"])})
        else:
            top_domains.append({"domain": item["domain"], "seconds": int(item.get("count", 0)) * 30})
    category_breakdown: dict[str, int] = {}
    for item in categories:
        category_breakdown[str(item.get("category", "other"))] = int(item.get("count", 0))
    top_category = "other"
    if category_breakdown:
        top_category = max(category_breakdown, key=lambda k: category_breakdown[k])
    productive = min(100, max(0, 40 + events // 5))
    if category_breakdown.get("study", 0) > category_breakdown.get("social", 0):
        productive = min(100, productive + 15)
    return {
        "connected": events > 0,
        "events_today": events,
        "domains": domains,
        "total_events": events,
        "top_category": top_category,
        "avg_productivity_score": productive,
        "top_domains": top_domains,
        "recent_sites": [d["domain"] for d in top_domains[:5]],
        "category_breakdown": category_breakdown,
        "date": raw.get("date"),
        "source": raw.get("source"),
    }


@router.get("/api/behavior/stats")
def behavior_stats(
    day: str | None = Query(None, description="YYYY-MM-DD or today"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if day in (None, "today", "now"):
        d = date.today()
    else:
        d = date.fromisoformat(day)

    payload = _stats_from_db(db, user.id, d)
    if payload["events_today"] == 0:
        csv_stats = _stats_from_csv(d.isoformat())
        if csv_stats and csv_stats["events_today"] > 0:
            return _shape_stats_for_ui(csv_stats)
    if payload["events_today"] == 0:
        return _shape_stats_for_ui({**payload, "events_today": 0})
    return _shape_stats_for_ui(payload)
