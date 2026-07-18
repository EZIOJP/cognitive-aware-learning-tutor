"""Bridge desktop tracker SESSION_END events into timetable tracked_sessions."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from backend.models.timetable import TrackedSession
from backend.behavior.classification_service import normalize_title_key


def _resolve_category_from_cache(db: Session, *, exe: str, title: str, category: str) -> tuple[str, str]:
    """Always apply approved classification cache (not only Other/Browser)."""
    from backend.models.app_classification import AppClassificationCache

    if exe:
        cached = (
            db.query(AppClassificationCache)
            .filter(AppClassificationCache.key == exe.strip())
            .first()
        )
        if cached:
            return cached.category, "llm_reviewed"

    if title:
        title_key = normalize_title_key(str(title))
        if title_key:
            cached = (
                db.query(AppClassificationCache)
                .filter(AppClassificationCache.key == title_key)
                .first()
            )
            if cached:
                return cached.category, "llm_reviewed"

    # Policy app_overrides (any user — applied at ingest for matching keys)
    # Per-user overrides are applied at score-resolve time; cache is global.

    return category, "rule"


def _session_id_from_event(payload: dict) -> str:
    if payload.get("session_id"):
        return str(payload["session_id"])
    raw = (
        f"{payload.get('source', '')}|{payload.get('exe', '')}|"
        f"{payload.get('timestamp', '')}|{payload.get('end_timestamp', '')}"
    )
    return "desktop-" + hashlib.sha1(raw.encode()).hexdigest()[:24]


def _ms_to_dt(ms: int | float | None) -> datetime | None:
    if ms is None:
        return None
    try:
        return datetime.fromtimestamp(float(ms) / 1000.0, tz=UTC)
    except (TypeError, ValueError, OSError):
        return None


def ingest_desktop_session(db: Session, *, user_id: int, payload: dict) -> TrackedSession | None:
    """Persist a desktop_tracker SESSION_END into tracked_sessions (idempotent)."""
    if payload.get("type") != "SESSION_END":
        return None
    if payload.get("source") != "desktop_tracker":
        return None

    duration = int(payload.get("duration_seconds") or 0)
    if duration < 2:
        return None

    session_id = _session_id_from_event(payload)
    existing = db.query(TrackedSession).filter(TrackedSession.session_id == session_id).first()
    if existing:
        return existing

    start = _ms_to_dt(payload.get("timestamp"))
    end = _ms_to_dt(payload.get("end_timestamp"))
    if start is None or end is None:
        now = datetime.now(UTC)
        end = end or now
        start = start or end

    title = payload.get("title") or payload.get("window_title") or ""
    exe = payload.get("exe") or payload.get("domain") or ""
    category = str(payload.get("category") or "Other")
    category, category_source = _resolve_category_from_cache(
        db, exe=str(exe), title=str(title), category=category
    )
    # Per-user policy app overrides (score-time also applies; set category at ingest)
    from backend.behavior.productivity_policy import (
        load_policy_dict,
        resolve_category_with_overrides,
    )

    policy = load_policy_dict(db, user_id)
    overridden = resolve_category_with_overrides(
        category, app_name=str(exe), window_title=str(title), policy=policy
    )
    if overridden and overridden != category:
        category = overridden
        category_source = "policy_override"

    row = TrackedSession(
        session_id=session_id,
        user_id=user_id,
        task_id=None,
        start_time=start,
        end_time=end,
        source="desktop_tracker",
        category=category,
        window_title=str(title)[:512] if title else None,
        app_name=str(exe)[:255] if exe else None,
        category_source=category_source,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
