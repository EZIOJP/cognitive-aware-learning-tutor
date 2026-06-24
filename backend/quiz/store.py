"""Generic quiz session storage (vocab, math, study, code drills)."""

from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy.orm import Session

from backend.models import QuizSession


def create_global_session(
    db: Session,
    *,
    user_id: int,
    domain: str,
    payload: dict[str, Any],
    hub_session_id: int | None = None,
) -> str:
    external_id = str(uuid.uuid4())
    row = QuizSession(
        external_id=external_id,
        user_id=user_id,
        quiz_type=f"global_{domain}",
        word_ids_json=json.dumps({"domain": domain, "payload": payload}),
        current_index=0,
        attempts_json="[]",
        hub_session_id=hub_session_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return external_id


def load_global_session(db: Session, external_id: str, user_id: int) -> dict[str, Any] | None:
    row = (
        db.query(QuizSession)
        .filter(QuizSession.external_id == external_id, QuizSession.user_id == user_id)
        .first()
    )
    if not row:
        return None
    meta = json.loads(row.word_ids_json or "{}")
    return {
        "row": row,
        "domain": meta.get("domain", "study"),
        "payload": meta.get("payload", {}),
        "index": int(row.current_index),
        "attempts": json.loads(row.attempts_json or "[]"),
        "hub_session_id": row.hub_session_id,
    }


def save_global_session(db: Session, sess: dict[str, Any]) -> None:
    row: QuizSession = sess["row"]
    row.current_index = int(sess["index"])
    row.attempts_json = json.dumps(sess.get("attempts", []))
    db.add(row)
    db.commit()


def complete_global_session(db: Session, external_id: str, user_id: int) -> int | None:
    row = (
        db.query(QuizSession)
        .filter(QuizSession.external_id == external_id, QuizSession.user_id == user_id)
        .first()
    )
    if not row:
        return None
    from datetime import UTC, datetime

    row.completed_at = datetime.now(UTC)
    db.commit()
    return row.hub_session_id
