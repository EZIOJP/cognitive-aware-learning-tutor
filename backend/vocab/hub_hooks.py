from datetime import date

from sqlalchemy.orm import Session

from backend.hub.services.ingest import insert_reading
from backend.hub.services.rollup import rebuild_daily_rollup
from backend.hub.services.sessions import end_activity_session


def on_vocab_quiz_complete(
    db: Session,
    user_id: int,
    correct: int,
    total: int,
    *,
    hub_session_id: int | None = None,
) -> None:
    try:
        insert_reading(
            db,
            user_id=user_id,
            slug="vocab_quiz_complete",
            value_numeric=float(correct),
            value_json={"correct": correct, "total": total},
            source_device="vocab",
            session_id=hub_session_id,
        )
        if hub_session_id:
            end_activity_session(
                db,
                hub_session_id,
                user_id=user_id,
                metadata={"correct": correct, "total": total},
            )
        rebuild_daily_rollup(db, user_id, date.today())
    except ValueError:
        pass


def on_math_attempt(
    db: Session,
    user_id: int,
    is_correct: bool,
    topic: str,
    *,
    hub_session_id: int | None = None,
) -> None:
    try:
        insert_reading(
            db,
            user_id=user_id,
            slug="math_attempt",
            value_numeric=1.0 if is_correct else 0.0,
            value_json={"topic": topic, "is_correct": is_correct},
            source_device="math",
            session_id=hub_session_id,
        )
        rebuild_daily_rollup(db, user_id, date.today())
    except ValueError:
        pass


def on_face_status(db: Session, user_id: int, attention: float) -> None:
    try:
        insert_reading(
            db,
            user_id=user_id,
            slug="face_attention",
            value_numeric=float(attention),
            source_device="face_tracker",
        )
    except ValueError:
        pass


def on_global_quiz_complete(
    db: Session,
    user_id: int,
    correct: int,
    total: int,
    *,
    domain: str | None = None,
    hub_session_id: int | None = None,
) -> None:
    try:
        insert_reading(
            db,
            user_id=user_id,
            slug="global_quiz_complete",
            value_numeric=float(correct),
            value_json={"correct": correct, "total": total, "domain": domain},
            source_device="quiz",
            session_id=hub_session_id,
        )
        if hub_session_id:
            end_activity_session(
                db,
                hub_session_id,
                user_id=user_id,
                metadata={"correct": correct, "total": total, "domain": domain},
            )
        rebuild_daily_rollup(db, user_id, date.today())
    except ValueError:
        pass
