import json
import uuid
from typing import Any

from sqlalchemy.orm import Session

from backend.models import QuizSession


def create_quiz_session(
    db: Session,
    *,
    user_id: int,
    quiz_type: str,
    words: list[dict[str, Any]],
) -> str:
    external_id = str(uuid.uuid4())
    row = QuizSession(
        external_id=external_id,
        user_id=user_id,
        quiz_type=quiz_type,
        word_ids_json=json.dumps([int(w["id"]) for w in words]),
        current_index=0,
        attempts_json="[]",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    row._words_cache = words  # type: ignore[attr-defined]
    return external_id


def get_quiz_session(db: Session, external_id: str, user_id: int) -> dict[str, Any] | None:
    row = (
        db.query(QuizSession)
        .filter(QuizSession.external_id == external_id, QuizSession.user_id == user_id)
        .first()
    )
    if not row:
        return None
    words_cache = getattr(row, "_words_cache", None)
    if words_cache is None:
        from backend.vocab.words import load_words

        all_words = load_words()
        ids = set(json.loads(row.word_ids_json or "[]"))
        words_cache = [w for w in all_words if int(w["id"]) in ids] if ids else all_words
    return {
        "user_id": row.user_id,
        "words": words_cache,
        "index": row.current_index,
        "attempts": json.loads(row.attempts_json or "[]"),
        "quiz_type": row.quiz_type,
        "row": row,
    }


def save_quiz_session(db: Session, sess: dict[str, Any]) -> None:
    row: QuizSession = sess["row"]
    row.current_index = int(sess["index"])
    row.attempts_json = json.dumps(sess.get("attempts", []))
    db.add(row)
    db.commit()


def complete_quiz_session(db: Session, external_id: str, user_id: int) -> None:
    row = (
        db.query(QuizSession)
        .filter(QuizSession.external_id == external_id, QuizSession.user_id == user_id)
        .first()
    )
    if row:
        from datetime import UTC, datetime

        row.completed_at = datetime.now(UTC)
        db.commit()
