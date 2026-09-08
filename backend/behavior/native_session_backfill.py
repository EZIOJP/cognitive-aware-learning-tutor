"""Backfill category on native-written tracked_sessions (code maturity F2)."""

from __future__ import annotations

import logging

from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.behavior.tracker_classify import classify_app
from backend.models.timetable import TrackedSession

log = logging.getLogger("calt.native_session_backfill")


def backfill_native_session_categories(
    db: Session,
    *,
    user_id: int | None = None,
    limit: int = 40,
) -> int:
    """Set category for rows with category_source=native and empty category.

    Uses the same classify_app rules as Python TrackerService.
    Returns number of rows updated.
    """
    q = db.query(TrackedSession).filter(
        TrackedSession.category_source == "native",
        or_(TrackedSession.category.is_(None), TrackedSession.category == ""),
    )
    if user_id is not None:
        q = q.filter(TrackedSession.user_id == int(user_id))
    rows = q.order_by(TrackedSession.start_time.desc()).limit(max(1, int(limit))).all()
    n = 0
    for row in rows:
        exe = str(row.app_name or "")
        title = str(row.window_title or "")
        try:
            cat, _score = classify_app(exe, title)
        except Exception as exc:  # noqa: BLE001
            log.debug("classify skip %s: %s", row.session_id, exc)
            continue
        if not cat:
            continue
        row.category = cat
        # Keep category_source=native so we know origin; mark rule as applied.
        n += 1
    if n:
        try:
            db.commit()
        except Exception as exc:  # noqa: BLE001
            log.debug("backfill commit failed: %s", exc)
            try:
                db.rollback()
            except Exception:  # noqa: BLE001
                pass
            return 0
    return n


def maybe_backfill_for_user(user_id: int, *, limit: int = 40) -> int:
    """Open a short-lived session and backfill. Safe for UI timers."""
    if int(user_id or 0) <= 0:
        return 0
    from backend.db.base import SessionLocal

    db = SessionLocal()
    try:
        return backfill_native_session_categories(db, user_id=int(user_id), limit=limit)
    except Exception as exc:  # noqa: BLE001
        log.debug("maybe_backfill: %s", exc)
        return 0
    finally:
        db.close()


# Back-compat alias — Focus should import from native_enforcer_status instead.
def enforcer_maturity_block():
    from backend.behavior.native_enforcer_status import enforcer_maturity_block as _block

    return _block()
