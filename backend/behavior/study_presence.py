"""CALT SPA productive presence → tracked_sessions (active tab / focused only).

Productive SPA credit is limited to:
  - Lecture Notes (document open + reading)
  - Review Hub / quiz (`/review`)
  - GRE vocab (`/gre-vocab`)
  - Math tutor / practice (`/math-tutor`)

Bible is spiritual (not credited here). Other CALT routes are ignored.
Internet sites are owned by the Edge SelfTracker extension (active tab only).
"""

from __future__ import annotations

import hashlib
import time
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from backend.timetable.tracker_bridge import ingest_behavior_session

# Credit at most this many seconds per heartbeat (matches ~60s client poll).
_MAX_CREDIT_S = 70
_MIN_CREDIT_S = 15
_MIN_GAP_S = 20

# In-memory last heartbeat per (user, lane) — process-local.
_last_at: dict[str, float] = {}

_LANE_LECTURE = "lecture_notes"
_LANE_QUIZ = "quiz"
_LANE_VOCAB = "vocab"
_LANE_MATH = "math"


def _norm_path(path: str) -> str:
    p = (path or "/").strip() or "/"
    if "?" in p:
        p = p.split("?", 1)[0]
    if "#" in p:
        p = p.split("#", 1)[0]
    if not p.startswith("/"):
        p = "/" + p
    return p


def path_is_lecture_notes(path: str) -> bool:
    p = _norm_path(path)
    return p == "/lecture-notes" or p.startswith("/lecture-notes/")


def path_is_quiz(path: str) -> bool:
    p = _norm_path(path)
    return p == "/review" or p.startswith("/review/")


def path_is_vocab(path: str) -> bool:
    p = _norm_path(path)
    return p == "/gre-vocab" or p.startswith("/gre-vocab/")


def path_is_math(path: str) -> bool:
    p = _norm_path(path)
    return p == "/math-tutor" or p.startswith("/math-tutor/")


def path_is_bible(path: str) -> bool:
    p = _norm_path(path)
    return p == "/bible" or p.startswith("/bible/")


def path_is_study(path: str) -> bool:
    """Legacy alias: lecture-notes only (tests + older callers)."""
    return path_is_lecture_notes(path)


def resolve_calt_lane(path: str) -> str | None:
    """Return productive lane id, or None if path should not earn SPA credit."""
    if path_is_bible(path):
        return None
    if path_is_lecture_notes(path):
        return _LANE_LECTURE
    if path_is_quiz(path):
        return _LANE_QUIZ
    if path_is_vocab(path):
        return _LANE_VOCAB
    if path_is_math(path):
        return _LANE_MATH
    return None


def _lane_meta(lane: str) -> tuple[str, str]:
    """category, title prefix."""
    if lane == _LANE_LECTURE:
        return "Study (Browser)", "CALT Lecture Notes"
    if lane == _LANE_QUIZ:
        return "Study (Browser)", "CALT Quiz / Review"
    if lane == _LANE_VOCAB:
        return "Study (Browser)", "CALT GRE Vocab"
    if lane == _LANE_MATH:
        return "Study (Browser)", "CALT Math"
    return "Study (Browser)", "CALT Study"


def apply_study_presence(
    db: Session,
    *,
    user_id: int,
    path: str,
    focused: bool = True,
    client: str | None = None,
    title: str | None = None,
    notes_loaded: bool = False,
    reading: bool = False,
    document_id: str | None = None,
) -> dict[str, Any]:
    """Credit focused time on productive CALT lanes only (active / focused tab)."""
    if not focused:
        return {"ok": True, "credited_seconds": 0, "reason": "unfocused"}

    if path_is_bible(path):
        return {"ok": True, "credited_seconds": 0, "reason": "spiritual_not_productive"}

    lane = resolve_calt_lane(path)
    if not lane:
        return {"ok": True, "credited_seconds": 0, "reason": "not_productive_calt"}

    if lane == _LANE_LECTURE and (not notes_loaded or not reading):
        return {"ok": True, "credited_seconds": 0, "reason": "notes_not_reading"}

    throttle_key = f"{user_id}:{lane}"
    now = time.time()
    last = float(_last_at.get(throttle_key) or 0)
    if last and (now - last) < _MIN_GAP_S:
        return {"ok": True, "credited_seconds": 0, "reason": "throttled"}

    gap = (now - last) if last else float(_MAX_CREDIT_S)
    credit = int(min(_MAX_CREDIT_S, max(_MIN_CREDIT_S, gap)))
    _last_at[throttle_key] = now

    end_ms = int(now * 1000)
    start_ms = end_ms - credit * 1000
    client_tag = (client or "web").strip().lower()[:32]
    path_clean = _norm_path(path)[:200]
    doc = (document_id or "").strip()[:200]
    title_s = (title or doc or path_clean)[:200]
    bucket = int(now // 60)
    sid_raw = f"calt_spa|{user_id}|{lane}|{path_clean}|{doc}|{bucket}|{client_tag}"
    session_id = "spa-" + hashlib.sha1(sid_raw.encode()).hexdigest()[:24]

    category, label = _lane_meta(lane)
    if doc:
        label = f"{label} · {doc}"
    elif title_s and title_s != path_clean:
        label = f"{label} · {title_s}"

    payload = {
        "type": "SESSION_END",
        "source": "calt_spa",
        "session_id": session_id,
        "timestamp": start_ms,
        "end_timestamp": end_ms,
        "duration_seconds": credit,
        "category": category,
        "title": label[:512],
        "exe": f"calt_spa:{client_tag}",
        "app_name": f"calt_spa:{client_tag}",
        "path": path_clean,
        "document_id": doc or None,
        "lane": lane,
    }
    row = ingest_behavior_session(db, user_id=user_id, payload=payload)
    return {
        "ok": True,
        "credited_seconds": credit if row else 0,
        "session_id": session_id if row else None,
        "path": path_clean,
        "document_id": doc or None,
        "client": client_tag,
        "lane": lane,
        "at": datetime.now(UTC).isoformat(),
    }
