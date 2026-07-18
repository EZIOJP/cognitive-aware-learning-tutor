"""Browser behavior WebSocket + stats — hub readings (DB) with optional CSV mirror."""

from __future__ import annotations

import asyncio
import csv
import json
import logging
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from backend.core.auth import decode_user, ensure_demo_user, get_current_user
from backend.db.base import SessionLocal
from backend.db.session import get_db
from backend.hub.services.ingest import insert_reading
from backend.models import Reading, ReadingDefinition, User
from backend.models.timetable import TrackedSession
from backend.paths import DATA_LOGS_DIR
from backend.timetable.tracker_query import primary_tracker_user_id, tracker_user_ids
from backend.planner.service import iso_utc
from backend.behavior.session_key import is_browser_exe

router = APIRouter(tags=["behavior"])
log = logging.getLogger(__name__)

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


def _persist_behavior_event(enriched: dict, token: str | None) -> None:
    """Sync DB ingest — run in a thread pool so WS keepalives stay responsive."""
    db = SessionLocal()
    try:
        user = _user_from_ws_token(token, db)
        source = str(enriched.get("source") or "extension")
        device = "desktop_tracker" if source == "desktop_tracker" else "extension"
        insert_reading(
            db,
            user_id=user.id,
            slug="browser_event",
            value_json=enriched,
            source_device=device,
            client_event_id=enriched.get("event_id") or enriched.get("received_at"),
        )
        if enriched.get("type") == "SESSION_END" and source == "desktop_tracker":
            from backend.timetable.tracker_bridge import ingest_desktop_session

            ingest_desktop_session(db, user_id=user.id, payload=enriched)
    except (ValueError, Exception) as exc:
        log.debug("behavior ws persist skipped: %s", exc)
    finally:
        db.close()


def _persist_behavior_batch(events: list[dict], token: str | None) -> int:
    """Persist a BATCH of browser/extension events in one DB session."""
    if not events:
        return 0
    db = SessionLocal()
    n = 0
    try:
        user = _user_from_ws_token(token, db)
        for data in events:
            enriched = {**data, "received_at": datetime.now(UTC).isoformat()}
            source = str(enriched.get("source") or "extension")
            device = "desktop_tracker" if source == "desktop_tracker" else "extension"
            try:
                insert_reading(
                    db,
                    user_id=user.id,
                    slug="browser_event",
                    value_json=enriched,
                    source_device=device,
                    client_event_id=enriched.get("event_id") or enriched.get("received_at"),
                )
                n += 1
            except (ValueError, Exception) as exc:
                log.debug("batch event skipped: %s", exc)
        return n
    finally:
        db.close()


def _user_from_ws_token(token: str | None, db: Session) -> User:
    if token:
        user = decode_user(token, db)
        if user:
            return user
    return ensure_demo_user(db)


@router.websocket("/ws/behavior")
async def behavior_websocket(websocket: WebSocket):
    await websocket.accept()
    today_str = datetime.now(UTC).strftime("%Y-%m-%d")
    token = websocket.query_params.get("token")
    if not token:
        qs = parse_qs(websocket.scope.get("query_string", b"").decode())
        token = (qs.get("token") or [None])[0]

    try:
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "BATCH" and isinstance(data.get("events"), list):
                events = [e for e in data["events"] if isinstance(e, dict)]
                for ev in events:
                    enriched = {**ev, "received_at": datetime.now(UTC).isoformat()}
                    await asyncio.to_thread(_append_csv, enriched, today_str)
                wrote = await asyncio.to_thread(_persist_behavior_batch, events, token)
                await websocket.send_json({"status": "ok", "batched": wrote})
                continue

            enriched = {**data, "received_at": datetime.now(UTC).isoformat()}
            await asyncio.to_thread(_append_csv, enriched, today_str)
            # LIVE_SNAPSHOT is UI-only noise for DB — skip heavy ingest
            if enriched.get("type") != "LIVE_SNAPSHOT":
                await asyncio.to_thread(_persist_behavior_event, enriched, token)
            await websocket.send_json({"status": "ok"})
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        # Ping timeout during idle, tab reload, or uvicorn --reload — benign
        log.debug("behavior ws closed: %s", exc)


def _stats_from_db(db: Session, user_id: int, day: date) -> dict:
    from backend.behavior.domain_classify import classify_domain

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

    domain_seconds: Counter[str] = Counter()
    domain_events: Counter[str] = Counter()
    domain_category: dict[str, str] = {}
    domain_score: dict[str, int] = {}
    categories: Counter[str] = Counter()

    for row in rows:
        payload = json.loads(row.value_json) if row.value_json else {}
        if payload.get("source") == "desktop_tracker":
            continue
        domain = (
            payload.get("domain")
            or (payload.get("url") or "unknown")[:48]
            or "unknown"
        )
        title = payload.get("title") or ""
        dur = int(payload.get("duration_seconds") or 30)

        cat, score = classify_domain(domain, title)

        domain_seconds[domain] += dur
        domain_events[domain] += 1
        if domain not in domain_category:
            domain_category[domain] = cat
            domain_score[domain] = score
        categories[cat] += dur

    top_domains = [
        {
            "domain": d,
            "seconds": domain_seconds[d],
            "count": domain_events[d],
            "category": domain_category.get(d, "Other (Browser)"),
            "productivity_score": domain_score.get(d, 35),
        }
        for d, _ in domain_seconds.most_common(15)
    ]
    top_categories = [
        {"category": k, "seconds": v}
        for k, v in categories.most_common(10)
    ]
    return {
        "events_today": sum(domain_events.values()),
        "domains": top_domains,
        "categories": top_categories,
        "source": "database",
        "date": day.isoformat(),
    }


def _stats_from_csv(day_str: str) -> dict | None:
    from backend.behavior.domain_classify import classify_domain, classify_browser_title

    csv_path = LOG_DIR / f"DSC_browser_behavior_{day_str}.csv"
    if not csv_path.exists():
        return None
    rows: list[dict] = []
    with open(csv_path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    domain_seconds: Counter[str] = Counter()
    domain_events: Counter[str] = Counter()
    domain_category: dict[str, str] = {}
    domain_score: dict[str, int] = {}
    categories: Counter[str] = Counter()

    for row in rows:
        exe = row.get("exe") or ""
        title = row.get("title") or ""
        domain = row.get("domain") or (row.get("url") or "unknown")[:48]
        dur = int(row.get("duration_seconds") or 30)

        is_browser = is_browser_exe(exe)
        if is_browser:
            cat, score = classify_browser_title(title)
        elif domain and domain != exe:
            cat, score = classify_domain(domain, title)
        else:
            cat = row.get("category") or "Other"
            try:
                score = int(row.get("productivity_score") or 35)
            except (TypeError, ValueError):
                score = 35

        display_key = domain if (domain and domain != exe) else (
            title.split(" - ")[0][:40] if title else exe
        )
        if is_browser:
            display_key = title.split(" - ")[0][:40] if title else domain

        domain_seconds[display_key] += dur
        domain_events[display_key] += 1
        if display_key not in domain_category:
            domain_category[display_key] = cat
            domain_score[display_key] = score
        categories[cat] += dur

    top_domains = [
        {
            "domain": d,
            "seconds": domain_seconds[d],
            "count": domain_events[d],
            "category": domain_category.get(d, "Other (Browser)"),
            "productivity_score": domain_score.get(d, 35),
        }
        for d, _ in domain_seconds.most_common(15)
    ]
    top_categories = [
        {"category": k, "seconds": v}
        for k, v in categories.most_common(10)
    ]
    return {
        "events_today": sum(domain_events.values()),
        "domains": top_domains,
        "categories": top_categories,
        "source": "csv_fallback",
        "date": day_str,
    }


def _shape_stats_for_ui(raw: dict) -> dict:
    """Normalize DB/CSV stats for dashboard widget."""
    events = raw.get("events_today", 0)
    domains = raw.get("domains") or []
    categories = raw.get("categories") or []

    top_domains = []
    for item in domains[:12]:
        secs = int(item.get("seconds", 0)) or int(item.get("count", 0)) * 30
        top_domains.append({
            "domain": item["domain"],
            "seconds": secs,
            "category": item.get("category", "Other (Browser)"),
            "productivity_score": int(item.get("productivity_score", 35)),
        })

    category_breakdown: dict[str, int] = {}
    for item in categories:
        cat = str(item.get("category", "other"))
        val = int(item.get("seconds", 0)) or int(item.get("count", 0))
        category_breakdown[cat] = category_breakdown.get(cat, 0) + val

    top_category = "other"
    if category_breakdown:
        top_category = max(category_breakdown, key=lambda k: category_breakdown[k])

    total_seconds = sum(d["seconds"] for d in top_domains)
    if total_seconds > 0 and top_domains:
        weighted = sum(d["seconds"] * d["productivity_score"] for d in top_domains)
        avg_score = round(weighted / total_seconds)
    else:
        avg_score = 0

    return {
        "connected": events > 0,
        "events_today": events,
        "domains": domains,
        "total_events": events,
        "top_category": top_category,
        "avg_productivity_score": avg_score,
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
    from backend.behavior.category_scores import load_score_map

    scores = load_score_map(db)
    if payload["events_today"] == 0:
        desktop_browser = _browser_stats_from_tracked_sessions(db, tracker_user_ids(db, user), d)
        if desktop_browser and desktop_browser["events_today"] > 0:
            return _shape_stats_for_ui(desktop_browser)
        csv_stats = _stats_from_csv(d.isoformat())
        if csv_stats and csv_stats["events_today"] > 0:
            return _shape_stats_for_ui(csv_stats)
        desktop_csv = _browser_stats_from_desktop_csv(d.isoformat(), scores=scores)
        if desktop_csv and desktop_csv["events_today"] > 0:
            return _shape_stats_for_ui(desktop_csv)
    if payload["events_today"] == 0:
        return _shape_stats_for_ui({**payload, "events_today": 0})
    return _shape_stats_for_ui(payload)


def _browser_stats_from_tracked_sessions(db: Session, user_ids: list[int], day: date) -> dict | None:
    """Browser site breakdown from desktop tracker rows (no Chrome extension needed)."""
    from backend.behavior.category_scores import load_score_map
    from backend.behavior.session_merge import merge_tracked_rows
    from backend.behavior.stats_aggregate import aggregate_session_rows, browser_domains_payload

    start, end = _day_bounds(day)
    rows = (
        db.query(TrackedSession)
        .filter(
            TrackedSession.user_id.in_(user_ids),
            TrackedSession.source == "desktop_tracker",
            TrackedSession.start_time >= start,
            TrackedSession.start_time < end,
        )
        .order_by(TrackedSession.start_time)
        .all()
    )
    if not rows:
        return None
    rows = merge_tracked_rows(rows)
    scores = load_score_map(db)
    buckets, _ = aggregate_session_rows(rows, scores=scores)
    domains, categories, events = browser_domains_payload(buckets)
    if events == 0:
        return None
    return {
        "events_today": events,
        "domains": domains,
        "categories": categories,
        "source": "desktop_tracker",
        "date": day.isoformat(),
    }


def _browser_stats_from_desktop_csv(day_str: str, *, scores: dict[str, int]) -> dict | None:
    """Browser sites from desktop tracker CSV when DB is empty."""
    from backend.behavior.stats_aggregate import aggregate_session_rows, browser_domains_payload

    csv_path = LOG_DIR / f"DSC_desktop_behavior_{day_str}.csv"
    if not csv_path.exists():
        return None
    with open(csv_path, encoding="utf-8") as f:
        raw_rows = list(csv.DictReader(f))
    if not raw_rows:
        return None

    dict_rows = []
    for row in raw_rows:
        start_ms = row.get("timestamp")
        end_ms = row.get("end_timestamp")
        if not start_ms or not end_ms:
            continue
        try:
            start = datetime.fromtimestamp(float(start_ms) / 1000.0, tz=UTC)
            end = datetime.fromtimestamp(float(end_ms) / 1000.0, tz=UTC)
        except (TypeError, ValueError, OSError):
            continue
        dict_rows.append({
            "app_name": row.get("exe"),
            "window_title": row.get("title"),
            "domain": row.get("domain"),
            "category": row.get("category"),
            "start_time": start,
            "end_time": end,
        })

    buckets, _ = aggregate_session_rows(dict_rows, scores=scores)
    domains, categories, events = browser_domains_payload(buckets)
    if events == 0:
        return None
    return {
        "events_today": events,
        "domains": domains,
        "categories": categories,
        "source": "desktop_tracker_csv",
        "date": day_str,
    }


# ── Desktop app stats (from desktop_tracker events) ──────────────────────────

TRACKER_ALIVE_SECONDS = 300


def _ensure_tracker_backfill(db: Session, user_ids: list[int], day: date) -> int:
    """Import any desktop CSV rows missing from tracked_sessions."""
    from backend.behavior.csv_backfill import maybe_backfill_day

    targets = set(user_ids)
    targets.add(primary_tracker_user_id(db))
    total = 0
    for uid in targets:
        total += maybe_backfill_day(db, uid, day)
    return total


def _tracker_alive(last_at: datetime | None, *, process_alive: bool) -> bool:
    if process_alive:
        return True
    if not last_at:
        return False
    return (_as_utc(datetime.now(UTC)) - _as_utc(last_at)).total_seconds() < TRACKER_ALIVE_SECONDS


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _day_bounds(day: date) -> tuple[datetime, datetime]:
    """Host-local calendar day as UTC instants (matches planner adherence)."""
    from backend.planner.service import local_day_bounds_utc

    return local_day_bounds_utc(day)


def _desktop_stats_from_tracked_sessions(
    db: Session, user_ids: list[int], day: date, *, user_id: int | None = None
) -> dict:
    """Primary: aggregate from tracked_sessions (standalone tracker SQLite writes)."""
    from backend.behavior.category_scores import load_score_map
    from backend.behavior.productivity_policy import load_policy_dict
    from backend.behavior.session_merge import merge_tracked_rows

    scores = load_score_map(db)
    policy = load_policy_dict(db, user_id) if user_id is not None else None

    start, end = _day_bounds(day)
    rows = (
        db.query(TrackedSession)
        .filter(
            TrackedSession.user_id.in_(user_ids),
            TrackedSession.source == "desktop_tracker",
            TrackedSession.start_time >= start,
            TrackedSession.start_time < end,
        )
        .order_by(TrackedSession.start_time)
        .all()
    )
    rows = merge_tracked_rows(rows)

    from backend.behavior.stats_aggregate import (
        aggregate_session_rows,
        desktop_sessions_payload,
    )

    buckets, total = aggregate_session_rows(rows, scores=scores, policy=policy)
    sessions = desktop_sessions_payload(buckets)

    weighted = 0
    for s in sessions:
        if s.get("kind") == "browser" and s.get("sites"):
            for site in s["sites"]:
                weighted += site["seconds"] * site["productivity_score"]
        else:
            weighted += s["seconds"] * s["productivity_score"]
    avg_score = round(weighted / total) if total else 0

    last_end = None
    if rows:
        last_end = max((r.end_time for r in rows if r.end_time), default=None)

    tracker_alive = False
    if last_end:
        tracker_alive = (_as_utc(datetime.now(UTC)) - _as_utc(last_end)).total_seconds() < TRACKER_ALIVE_SECONDS

    return {
        "sessions": sessions,
        "total_seconds": total,
        "avg_productivity_score": avg_score,
        "source": "tracked_sessions",
        "date": day.isoformat(),
        "tracker_running": tracker_alive or total > 0,
        "last_event_at": iso_utc(last_end),
    }


def _desktop_stats_from_readings(db: Session, user_id: int, day: date) -> dict:
    """Fallback: per-app time from hub readings (legacy WebSocket path)."""
    defn = db.query(ReadingDefinition).filter(ReadingDefinition.slug == "browser_event").first()
    if not defn:
        return {"sessions": [], "total_seconds": 0, "source": "database", "date": day.isoformat()}

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

    app_seconds: Counter[str] = Counter()
    app_category: dict[str, str] = {}
    app_score: dict[str, int] = {}
    total = 0

    for row in rows:
        try:
            payload = json.loads(row.value_json) if row.value_json else {}
        except json.JSONDecodeError:
            continue
        if payload.get("source") != "desktop_tracker":
            continue
        exe = payload.get("exe") or payload.get("domain") or "unknown"
        dur = int(payload.get("duration_seconds") or 0)
        if dur <= 0:
            continue
        app_seconds[exe] += dur
        total += dur
        if exe not in app_category:
            app_category[exe] = payload.get("category") or "Other"
        if exe not in app_score:
            try:
                app_score[exe] = int(payload.get("productivity_score") or 0)
            except (TypeError, ValueError):
                app_score[exe] = 0

    sessions = [
        {
            "exe": exe,
            "seconds": secs,
            "category": app_category.get(exe, "Other"),
            "productivity_score": app_score.get(exe, 35),
        }
        for exe, secs in app_seconds.most_common(20)
    ]

    avg_score = 0
    if sessions:
        weighted = sum(s["seconds"] * s["productivity_score"] for s in sessions)
        avg_score = round(weighted / total) if total else 0

    return {
        "sessions": sessions,
        "total_seconds": total,
        "avg_productivity_score": avg_score,
        "source": "database",
        "date": day.isoformat(),
        "tracker_running": total > 0,
    }

def _desktop_stats_from_csv(day_str: str, *, scores: dict[str, int]) -> dict | None:
    from backend.behavior.stats_aggregate import aggregate_session_rows, desktop_sessions_payload

    csv_path = LOG_DIR / f"DSC_desktop_behavior_{day_str}.csv"
    if not csv_path.exists():
        return None

    dict_rows = []
    with open(csv_path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            start_ms = row.get("timestamp")
            end_ms = row.get("end_timestamp")
            dur = int(row.get("duration_seconds") or 0)
            if dur <= 0 and (not start_ms or not end_ms):
                continue
            try:
                if start_ms and end_ms:
                    start = datetime.fromtimestamp(float(start_ms) / 1000.0, tz=UTC)
                    end = datetime.fromtimestamp(float(end_ms) / 1000.0, tz=UTC)
                else:
                    continue
            except (TypeError, ValueError, OSError):
                continue
            dict_rows.append({
                "app_name": row.get("exe"),
                "window_title": row.get("title"),
                "domain": row.get("domain"),
                "category": row.get("category"),
                "start_time": start,
                "end_time": end,
            })

    if not dict_rows:
        return None

    buckets, total = aggregate_session_rows(dict_rows, scores=scores)
    sessions = desktop_sessions_payload(buckets)

    weighted = 0
    for s in sessions:
        if s.get("kind") == "browser" and s.get("sites"):
            for site in s["sites"]:
                weighted += site["seconds"] * site["productivity_score"]
        else:
            weighted += s["seconds"] * s["productivity_score"]
    avg_score = round(weighted / total) if total else 0

    return {
        "sessions": sessions,
        "total_seconds": total,
        "avg_productivity_score": avg_score,
        "source": "csv_fallback (Lite Mode)",
        "date": day_str,
        "tracker_running": True,
    }

@router.get("/api/behavior/desktop-stats")
def desktop_stats(
    day: str | None = Query(None, description="YYYY-MM-DD or today"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Per-app time breakdown from the desktop tracker subprocess."""
    if day in (None, "today", "now"):
        d = date.today()
    else:
        d = date.fromisoformat(day)

    user_ids = tracker_user_ids(db, user)
    _ensure_tracker_backfill(db, user_ids, d)
    from backend.behavior.category_scores import load_score_map

    scores = load_score_map(db)
    payload = _desktop_stats_from_tracked_sessions(db, user_ids, d, user_id=user.id)
    if payload["total_seconds"] == 0:
        legacy = _desktop_stats_from_readings(db, user.id, d)
        if legacy["total_seconds"] > 0:
            return legacy
        csv_stats = _desktop_stats_from_csv(d.isoformat(), scores=scores)
        if csv_stats and csv_stats["total_seconds"] > 0:
            return csv_stats

    return payload


@router.get("/api/behavior/tracker-health")
def tracker_health(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Whether standalone tracker has written recently."""
    from backend.behavior.tracker_status import count_tracker_processes, tracker_process_detail

    today = date.today()
    start, end = _day_bounds(today)
    user_ids = tracker_user_ids(db, user)
    _ensure_tracker_backfill(db, user_ids, today)
    proc = tracker_process_detail()
    duplicate_processes = count_tracker_processes()

    rows = (
        db.query(TrackedSession)
        .filter(
            TrackedSession.user_id.in_(user_ids),
            TrackedSession.source == "desktop_tracker",
            TrackedSession.start_time >= start,
            TrackedSession.start_time < end,
        )
        .all()
    )
    last_at = max((r.end_time for r in rows if r.end_time), default=None)
    total_seconds = 0
    for row in rows:
        if row.start_time and row.end_time:
            total_seconds += max(0, int((row.end_time - row.start_time).total_seconds()))

    alive = _tracker_alive(last_at, process_alive=proc["process_alive"])

    if alive:
        status = "running"
    elif last_at:
        status = "stale"
    else:
        status = "no_data"

    hint = None
    if duplicate_processes > 1:
        hint = f"{duplicate_processes} tracker processes running — run scripts\\desktop_tracker\\stop_desktop_tracker.bat then start one."

    return {
        "tracker_alive": alive,
        "status": status,
        "last_event_at": iso_utc(last_at),
        "sessions_today": len(rows),
        "total_seconds_today": total_seconds,
        "source": "tracked_sessions",
        "process_alive": proc["process_alive"],
        "checkpoint_age_s": proc["checkpoint_age_s"],
        "log_age_s": proc["log_age_s"],
        "tracker_process_count": duplicate_processes,
        "hint": hint,
    }


@router.get("/api/behavior/desktop-timeline")
def desktop_timeline(
    day: str | None = Query(None, description="YYYY-MM-DD or today"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Ordered session intervals for timeline infographics."""
    from backend.behavior.session_merge import merge_tracked_rows

    if day in (None, "today", "now"):
        d = date.today()
    else:
        d = date.fromisoformat(day)

    user_ids = tracker_user_ids(db, user)
    _ensure_tracker_backfill(db, user_ids, d)
    start, end = _day_bounds(d)
    rows = (
        db.query(TrackedSession)
        .filter(
            TrackedSession.user_id.in_(user_ids),
            TrackedSession.source == "desktop_tracker",
            TrackedSession.start_time >= start,
            TrackedSession.start_time < end,
        )
        .order_by(TrackedSession.start_time)
        .all()
    )
    rows = merge_tracked_rows(rows)

    from backend.behavior.session_key import is_browser_exe
    from backend.behavior.tracker_ignore import is_ignored_app
    from backend.behavior.stats_aggregate import site_label
    from backend.behavior.category_scores import load_score_map
    from backend.behavior.productivity_policy import (
        load_policy_dict,
        resolve_category_with_overrides,
        resolve_session_score,
    )

    scores = load_score_map(db)
    policy = load_policy_dict(db, user.id)
    intervals = []
    for row in rows:
        if is_ignored_app(row.app_name or "", row.window_title or ""):
            continue
        if not row.start_time or not row.end_time:
            continue
        dur = max(0, int((row.end_time - row.start_time).total_seconds()))
        if dur < 2:
            continue
        exe = row.app_name or ""
        title = row.window_title
        site = site_label(exe, title) if is_browser_exe(exe) else None
        cat = resolve_category_with_overrides(
            row.category, app_name=exe, window_title=title, policy=policy
        )
        intervals.append({
            "session_id": row.session_id,
            "start_time": iso_utc(row.start_time),
            "end_time": iso_utc(row.end_time),
            "duration_seconds": dur,
            "category": cat,
            "app_name": row.app_name,
            "window_title": row.window_title,
            "site": site,
            "productivity_score": resolve_session_score(row, scores, policy),
            "override_productive": row.override_productive,
        })

    return {
        "date": d.isoformat(),
        "intervals": intervals,
        "total_seconds": sum(i["duration_seconds"] for i in intervals),
    }


@router.post("/api/behavior/purge-tracked-app")
def purge_tracked_app(
    app: str = Query(..., description="App exe to remove e.g. zen.exe"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Delete existing tracked_sessions rows for an app (not a blacklist — future sessions still ingest)."""
    needle = app.strip().lower()
    if not needle:
        raise HTTPException(status_code=400, detail="app name required")

    user_ids = tracker_user_ids(db, user)
    rows = (
        db.query(TrackedSession)
        .filter(
            TrackedSession.user_id.in_(user_ids),
            TrackedSession.source == "desktop_tracker",
        )
        .all()
    )
    deleted = 0
    for row in rows:
        name = (row.app_name or "").lower()
        if name == needle or name.endswith(needle) or needle in name:
            db.delete(row)
            deleted += 1
    db.commit()
    return {"deleted": deleted, "app": app}


@router.post("/api/behavior/tracker-force-sync")
def tracker_force_sync(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Ask standalone desktop tracker to flush current session, then confirm via ack file."""
    from backend.behavior.tracker_storage import request_tracker_flush, wait_for_flush_ack

    since = request_tracker_flush()
    flushed = wait_for_flush_ack(since, timeout_s=4.0)

    from backend.behavior.csv_backfill import backfill_desktop_csv_to_db, invalidate_backfill_stamp

    today = date.today()
    user_ids = tracker_user_ids(db, user)
    for uid in user_ids:
        invalidate_backfill_stamp(uid, today)
        backfill_desktop_csv_to_db(db, uid, today, force=True)

    start, end = _day_bounds(today)
    rows = (
        db.query(TrackedSession)
        .filter(
            TrackedSession.user_id.in_(user_ids),
            TrackedSession.source == "desktop_tracker",
            TrackedSession.start_time >= start,
            TrackedSession.start_time < end,
        )
        .all()
    )
    last_at = max((r.end_time for r in rows if r.end_time), default=None)
    alive = False
    if last_at:
        alive = (_as_utc(datetime.now(UTC)) - _as_utc(last_at)).total_seconds() < TRACKER_ALIVE_SECONDS

    if flushed:
        message = "Tracker flushed current session."
    elif alive:
        message = "Tracker is running but did not acknowledge flush in time. Data may still refresh on next poll."
    else:
        message = "Tracker not running. Start scripts\\desktop_tracker\\run_desktop_tracker_headless.bat or tray app."

    return {
        "flushed": flushed,
        "tracker_running": alive,
        "last_event_at": iso_utc(last_at),
        "message": message,
    }


# ── Productivity policy + category scores + session override ─────────────────


@router.get("/api/behavior/policy")
def get_productivity_policy(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from backend.behavior.productivity_policy import get_or_create_policy, serialize_policy

    row = get_or_create_policy(db, user.id)
    return serialize_policy(row)


@router.get("/api/behavior/distraction-gate")
def get_distraction_gate(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Whether games/custom apps are hard-blocked until today's productive goal."""
    from backend.behavior.distraction_gate import compute_distraction_gate

    return compute_distraction_gate(db, user.id)


@router.put("/api/behavior/policy")
def put_productivity_policy(
    body: dict,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from backend.behavior.productivity_policy import update_policy

    try:
        return update_policy(db, user.id, body or {})
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/api/behavior/category-scores")
def get_category_scores(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from backend.behavior.category_scores import load_score_map, seed_category_scores
    from backend.models.category_score import CategoryScore

    scores = load_score_map(db)
    if not scores:
        seed_category_scores(db)
        scores = load_score_map(db)
    _ = user  # auth required
    rows = db.query(CategoryScore).order_by(CategoryScore.category).all()
    return {
        "scores": {r.category: r.score for r in rows},
        "threshold_hint": 60,
    }


@router.put("/api/behavior/category-scores")
def put_category_scores(
    body: dict,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from datetime import UTC, datetime

    from backend.models.category_score import CategoryScore

    scores = body.get("scores") if isinstance(body, dict) else None
    if not isinstance(scores, dict):
        raise HTTPException(status_code=400, detail="scores object required")
    now = datetime.now(UTC)
    updated = 0
    for cat, score in scores.items():
        cat_s = str(cat).strip()
        if not cat_s:
            continue
        try:
            val = int(score)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail=f"invalid score for {cat_s}") from None
        if val < 0 or val > 100:
            raise HTTPException(status_code=400, detail=f"score for {cat_s} must be 0–100")
        row = db.query(CategoryScore).filter(CategoryScore.category == cat_s).first()
        if row is None:
            db.add(CategoryScore(category=cat_s, score=val, updated_at=now))
        else:
            row.score = val
            row.updated_at = now
        updated += 1
    db.commit()
    _ = user
    from backend.behavior.category_scores import load_score_map

    return {"updated": updated, "scores": load_score_map(db)}


@router.patch("/api/behavior/tracked-sessions/{session_id}")
def patch_tracked_session(
    session_id: str,
    body: dict,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Edge-case override: change category and/or force productive flag."""
    from backend.behavior.classification_service import ALLOWED_CATEGORIES
    from backend.behavior.category_scores import load_score_map, serialize_tracked_session
    from backend.behavior.productivity_policy import load_policy_dict

    user_ids = tracker_user_ids(db, user)
    row = (
        db.query(TrackedSession)
        .filter(
            TrackedSession.session_id == session_id,
            TrackedSession.user_id.in_(user_ids),
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="session not found")

    if "category" in body and body["category"] is not None:
        cat = str(body["category"]).strip()
        if cat not in ALLOWED_CATEGORIES:
            raise HTTPException(status_code=400, detail=f"category must be one of allowed list")
        row.category = cat
        row.category_source = "user_override"

    if "override_productive" in body:
        val = body["override_productive"]
        if val is None:
            row.override_productive = None
        elif isinstance(val, bool):
            row.override_productive = val
        else:
            raise HTTPException(status_code=400, detail="override_productive must be bool or null")

    db.commit()
    db.refresh(row)
    scores = load_score_map(db)
    policy = load_policy_dict(db, user.id)
    return {"session": serialize_tracked_session(row, scores, policy)}

