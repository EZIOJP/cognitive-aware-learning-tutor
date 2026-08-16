"""Bridge SESSION_END events (desktop tracker + SelfTracker extension) → tracked_sessions."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from backend.models.timetable import TrackedSession
from backend.behavior.classification_service import normalize_title_key

_ALLOWED_SOURCES = frozenset({"desktop_tracker", "extension", "calt_spa"})

# Extension uses short labels; map to policy categories used by score tables.
_EXT_CATEGORY_MAP: dict[str, str] = {
    "Coursework": "Coursework (Browser)",
    "Research": "Research",
    "Dev / Docs": "Dev / Code",
    "Knowledge Work": "Knowledge Work",
    "Design": "Design",
    "Admin / Email": "Email / Calendar",
    "Communication": "Communication",
    "News": "News",
    "Browsing": "Other (Browser)",
    "Music": "Music / Media",
    "Shopping": "Shopping",
    "Social Media": "Social Media",
    "Video / Streaming": "Video Streaming",
    "Gaming": "Gaming",
    "Idle / New Tab": "Other (Browser)",
    "Unknown": "Other (Browser)",
}


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

    return category, "rule"


def _session_id_from_event(payload: dict) -> str:
    if payload.get("session_id"):
        return str(payload["session_id"])
    source = str(payload.get("source") or "desktop_tracker")
    raw = (
        f"{source}|{payload.get('exe', '')}|{payload.get('domain', '')}|"
        f"{payload.get('url', '')}|{payload.get('timestamp', '')}|"
        f"{payload.get('end_timestamp', '')}"
    )
    prefix = "ext-" if source == "extension" else ("spa-" if source == "calt_spa" else "desktop-")
    return prefix + hashlib.sha1(raw.encode()).hexdigest()[:24]


def _ms_to_dt(ms: int | float | None) -> datetime | None:
    if ms is None:
        return None
    try:
        return datetime.fromtimestamp(float(ms) / 1000.0, tz=UTC)
    except (TypeError, ValueError, OSError):
        return None


def _classify_extension_payload(payload: dict) -> tuple[str, str]:
    """URL-first classification for SelfTracker SESSION_END."""
    from backend.behavior.domain_classify import classify_domain

    domain = str(payload.get("domain") or "").strip().lower()
    url = str(payload.get("url") or "").strip()
    title = str(payload.get("title") or payload.get("window_title") or "")
    if not domain and url:
        try:
            domain = (urlparse(url).hostname or "").lower().removeprefix("www.")
        except Exception:  # noqa: BLE001
            domain = ""

    if domain or url:
        hay = domain or url
        cat, _score = classify_domain(hay, title or url)
        return cat, "url_rule"

    raw = str(payload.get("category") or "Other (Browser)")
    return _EXT_CATEGORY_MAP.get(raw, raw if "(Browser)" in raw or raw in _EXT_CATEGORY_MAP.values() else "Other (Browser)"), "extension_label"


def ingest_behavior_session(db: Session, *, user_id: int, payload: dict) -> TrackedSession | None:
    """Persist a SESSION_END from desktop tracker, extension, or CALT SPA."""
    if payload.get("type") != "SESSION_END":
        return None
    source = str(payload.get("source") or "").strip()
    if source not in _ALLOWED_SOURCES:
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
    url = str(payload.get("url") or "").strip()
    domain = str(payload.get("domain") or "").strip().lower()
    if not domain and url:
        try:
            domain = (urlparse(url).hostname or "").lower().removeprefix("www.")
        except Exception:  # noqa: BLE001
            domain = ""

    if source == "extension":
        category, category_source = _classify_extension_payload(payload)
        exe = (domain or str(payload.get("exe") or ""))[:255]
        # Richer label: page title + path (domain stays in app_name for site grouping).
        page = str(title).strip()
        path_hint = ""
        if url:
            try:
                path_hint = (urlparse(url).path or "").rstrip("/")
            except Exception:  # noqa: BLE001
                path_hint = ""
        if not page:
            page = url or domain or "Browser"
        elif path_hint and path_hint != "/" and path_hint not in page:
            page = f"{page} · {path_hint}"
        elif domain and domain.lower() not in page.lower():
            page = f"{page} · {domain}"
        title = page
    elif source == "calt_spa":
        category = str(payload.get("category") or "Study (Browser)")
        category_source = "spa_heartbeat"
        exe = str(payload.get("exe") or payload.get("app_name") or "calt_spa")[:255]
    else:
        exe = str(payload.get("exe") or payload.get("domain") or "")
        category = str(payload.get("category") or "Other")
        category, category_source = _resolve_category_from_cache(
            db, exe=str(exe), title=str(title), category=category
        )

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
        source=source,
        category=category,
        window_title=str(title)[:512] if title else None,
        app_name=str(exe)[:255] if exe else None,
        category_source=category_source,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def ingest_desktop_session(db: Session, *, user_id: int, payload: dict) -> TrackedSession | None:
    """Backward-compatible alias — desktop tracker still calls this name."""
    if payload.get("source") is None:
        payload = {**payload, "source": "desktop_tracker"}
    return ingest_behavior_session(db, user_id=user_id, payload=payload)
