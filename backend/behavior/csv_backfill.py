"""Backfill tracked_sessions from desktop tracker CSV when SQLite writes lag."""

from __future__ import annotations

import csv
import logging
import os
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.models.timetable import TrackedSession
from backend.paths import DATA_LOGS_DIR
from backend.timetable.tracker_bridge import _session_id_from_event, ingest_desktop_session

log = logging.getLogger(__name__)

_STAMP_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "CognitiveAwareTutor"
_BATCH_SIZE = 100


def _csv_path(day: date) -> Path:
    return DATA_LOGS_DIR / f"DSC_desktop_behavior_{day.isoformat()}.csv"


def _stamp_path(user_id: int, day: date) -> Path:
    return _STAMP_DIR / f"csv_backfill_{user_id}_{day.isoformat()}.stamp"


def _day_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, datetime.min.time()).replace(tzinfo=UTC)
    return start, start + timedelta(days=1)


def _csv_last_end_ms(path: Path) -> int | None:
    try:
        last_ms = None
        with open(path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                try:
                    end_ms = int(float(row.get("end_timestamp") or 0))
                    if end_ms > 0:
                        last_ms = max(last_ms or 0, end_ms)
                except (TypeError, ValueError):
                    continue
        return last_ms
    except OSError:
        return None


def backfill_needed(db: Session, user_id: int, day: date) -> bool:
    """True when CSV has rows newer than DB (or never backfilled for this CSV)."""
    path = _csv_path(day)
    if not path.is_file():
        return False

    csv_mtime = path.stat().st_mtime
    stamp = _stamp_path(user_id, day)
    if stamp.is_file() and stamp.stat().st_mtime >= csv_mtime:
        return False

    start, end = _day_bounds(day)
    db_last = (
        db.query(func.max(TrackedSession.end_time))
        .filter(
            TrackedSession.user_id == user_id,
            TrackedSession.source == "desktop_tracker",
            TrackedSession.start_time >= start,
            TrackedSession.start_time < end,
        )
        .scalar()
    )
    csv_last_ms = _csv_last_end_ms(path)
    if not csv_last_ms:
        return False
    if db_last is None:
        return True

    db_last_ms = int(db_last.timestamp() * 1000) if db_last.tzinfo else int(
        db_last.replace(tzinfo=UTC).timestamp() * 1000
    )
    return csv_last_ms > db_last_ms + 60_000


def _mark_backfilled(user_id: int, day: date, csv_path: Path) -> None:
    _STAMP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _stamp_path(user_id, day)
    stamp.write_text(str(csv_path.stat().st_mtime), encoding="utf-8")


def _row_to_payload(row: dict) -> dict | None:
    try:
        start_ms = float(row.get("timestamp") or 0)
        end_ms = float(row.get("end_timestamp") or 0)
        if start_ms <= 0 or end_ms <= 0:
            return None
        duration = int(row.get("duration_seconds") or 0)
        if duration < 2:
            duration = max(2, int((end_ms - start_ms) / 1000))
    except (TypeError, ValueError):
        return None

    return {
        "type": "SESSION_END",
        "source": "desktop_tracker",
        "exe": row.get("exe") or "",
        "title": row.get("title") or "",
        "domain": row.get("domain") or "",
        "category": row.get("category") or "Other",
        "duration_seconds": duration,
        "timestamp": int(start_ms),
        "end_timestamp": int(end_ms),
        "reason": row.get("reason") or "csv_backfill",
        "pid": row.get("pid") or 0,
    }


def _existing_ids_for_day(db: Session, user_id: int, day: date) -> set[str]:
    start, end = _day_bounds(day)
    rows = (
        db.query(TrackedSession.session_id)
        .filter(
            TrackedSession.user_id == user_id,
            TrackedSession.source == "desktop_tracker",
            TrackedSession.start_time >= start,
            TrackedSession.start_time < end,
        )
        .all()
    )
    return {r[0] for r in rows}


def backfill_desktop_csv_to_db(
    db: Session,
    user_id: int,
    day: date,
    *,
    force: bool = False,
) -> int:
    """Import missing desktop CSV rows. Returns newly ingested count."""
    path = _csv_path(day)
    if not path.is_file():
        return 0
    if not force and not backfill_needed(db, user_id, day):
        return 0

    try:
        with open(path, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
    except OSError:
        return 0

    if not rows:
        _mark_backfilled(user_id, day, path)
        return 0

    existing = _existing_ids_for_day(db, user_id, day)
    ingested = 0
    pending = 0

    for row in rows:
        payload = _row_to_payload(row)
        if not payload:
            continue
        sid = _session_id_from_event(payload)
        if sid in existing:
            continue
        try:
            result = ingest_desktop_session(db, user_id=user_id, payload=payload)
            if result:
                existing.add(sid)
                ingested += 1
                pending += 1
                if pending >= _BATCH_SIZE:
                    pending = 0
        except IntegrityError:
            db.rollback()
            existing = _existing_ids_for_day(db, user_id, day)
            continue

    _mark_backfilled(user_id, day, path)
    if ingested:
        log.info("Backfilled %s desktop tracker rows for %s", ingested, day.isoformat())
    return ingested


def maybe_backfill_day(db: Session, user_id: int, day: date) -> int:
    """Cheap no-op when CSV and DB are already in sync."""
    return backfill_desktop_csv_to_db(db, user_id, day, force=False)


def backfill_range(db: Session, user_id: int, start: datetime, end: datetime, *, force: bool = False) -> int:
    """Backfill each calendar day touched by [start, end]."""
    if start.tzinfo is None:
        start = start.replace(tzinfo=UTC)
    if end.tzinfo is None:
        end = end.replace(tzinfo=UTC)
    day = start.date()
    last = end.date()
    total = 0
    while day <= last:
        if force:
            total += backfill_desktop_csv_to_db(db, user_id, day, force=True)
        else:
            total += maybe_backfill_day(db, user_id, day)
        day += timedelta(days=1)
    return total


def invalidate_backfill_stamp(user_id: int, day: date | None = None) -> None:
    """Force next backfill check to run (e.g. after tracker force-sync)."""
    if day is not None:
        stamp = _stamp_path(user_id, day)
        if stamp.is_file():
            try:
                stamp.unlink()
            except OSError:
                pass
        return
    if not _STAMP_DIR.is_dir():
        return
    prefix = f"csv_backfill_{user_id}_"
    for stamp in _STAMP_DIR.glob(f"{prefix}*.stamp"):
        try:
            stamp.unlink()
        except OSError:
            pass
