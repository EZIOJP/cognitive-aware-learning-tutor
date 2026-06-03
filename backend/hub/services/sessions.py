"""Activity session lifecycle — links vocab quiz and math practice to hub sessions."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from backend.models import ActivitySession

SESSION_IDLE = timedelta(hours=2)


def start_activity_session(
    db: Session,
    *,
    user_id: int,
    session_type: str,
    metadata: dict[str, Any] | None = None,
) -> ActivitySession:
    sess = ActivitySession(
        user_id=user_id,
        session_type=session_type,
        metadata_json=json.dumps(metadata or {}),
    )
    db.add(sess)
    db.commit()
    db.refresh(sess)
    return sess


def end_activity_session(
    db: Session,
    session_id: int,
    *,
    user_id: int,
    metadata: dict[str, Any] | None = None,
) -> ActivitySession | None:
    sess = db.get(ActivitySession, session_id)
    if not sess or sess.user_id != user_id:
        return None
    if not sess.ended_at:
        sess.ended_at = datetime.now(UTC)
    if metadata is not None:
        sess.metadata_json = json.dumps(metadata)
    db.commit()
    db.refresh(sess)
    return sess


def get_or_open_activity_session(
    db: Session,
    *,
    user_id: int,
    session_type: str,
    metadata: dict[str, Any] | None = None,
) -> ActivitySession:
    """Reuse an open session of the same type if started within SESSION_IDLE."""
    now = datetime.now(UTC)
    open_sess = (
        db.query(ActivitySession)
        .filter(
            ActivitySession.user_id == user_id,
            ActivitySession.session_type == session_type,
            ActivitySession.ended_at.is_(None),
        )
        .order_by(ActivitySession.started_at.desc())
        .first()
    )
    if open_sess and open_sess.started_at:
        started = open_sess.started_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=UTC)
        if now - started < SESSION_IDLE:
            return open_sess
        open_sess.ended_at = now
        db.commit()

    return start_activity_session(
        db, user_id=user_id, session_type=session_type, metadata=metadata
    )
