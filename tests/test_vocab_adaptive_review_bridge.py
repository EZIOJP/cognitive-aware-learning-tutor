"""Adaptive GRE quiz answers must land in shared ReviewCard FSRS."""

import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.db.base import Base
from backend.models.review_card import ReviewCard
from backend.models.user import User
from backend.models.word import Word
from backend.vocab import routes as vocab_routes
from backend.vocab.quiz_store import create_quiz_session


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    db.add(User(id=1, username="bridge", password_hash="x"))
    payload = {
        "id": 42,
        "word": "abate",
        "meaning": "to lessen",
        "group_number": 1,
    }
    db.add(
        Word(
            id=42,
            word="abate",
            group_number=1,
            content_json=json.dumps(payload),
        )
    )
    db.commit()
    return db


def test_adaptive_quiz_answer_upserts_vocab_review_card():
    db = _session()
    words = [{"id": 42, "word": "abate", "meaning": "to lessen", "group_number": 1}]
    session_id = create_quiz_session(
        db,
        user_id=1,
        quiz_type="adaptive_group",
        words=words,
    )
    user = db.query(User).filter(User.id == 1).one()
    body = vocab_routes.QuizAnswerBody(word_id=42, answer="to lessen")

    out = vocab_routes.quiz_answer(session_id, body, db=db, user=user)
    assert out["is_correct"] is True

    cards = db.query(ReviewCard).filter(ReviewCard.user_id == 1, ReviewCard.domain == "vocab").all()
    assert len(cards) == 1
    assert cards[0].label == "abate"
    assert "42" in cards[0].item_key
    db.close()
