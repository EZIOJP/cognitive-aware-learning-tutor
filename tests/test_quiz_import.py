"""Tests for smart quiz import (tag resolution + multi-format parse + SRS seeding)."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.db.base import Base
from backend.models.review_card import ReviewCard
from backend.models.user import User
from backend.transcripts.quiz_import import (
    import_summary,
    parse_smart_quiz_import,
    resolve_quiz_tags,
)


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add(User(id=1, username="quiz_import_test", password_hash="x"))
    session.commit()
    yield session
    session.close()


NOTE_WITH_TOPICS = """
## Topic Index
- L2-T01 — NumPy arrays
- L2-T02 — Vectorization

### L2-T01 — NumPy arrays
NumPy arrays store homogeneous data in contiguous memory.

### L2-T02 — Vectorization
Vectorized operations avoid Python loops.
"""


def test_parse_json_with_topic_id():
    text = """[
      {
        "question": "What is vectorization?",
        "options": ["Loops", "Array ops", "Files", "SQL"],
        "answer_index": 1,
        "topic_id": "L2-T02"
      }
    ]"""
    qs = parse_smart_quiz_import(text)
    assert len(qs) == 1
    assert qs[0]["topic_id"] == "L2-T02"
    assert qs[0]["answer_index"] == 1


def test_parse_mcq_block_with_tag_preamble():
    text = """
topic_id: L2-T01
Tags: numpy, arrays

Question 1
What memory layout do NumPy arrays use?
A) Contiguous homogeneous
B) Linked list
C) Hash map
D) Stack only
Answer: A
"""
    qs = parse_smart_quiz_import(text)
    assert len(qs) == 1
    assert qs[0]["topic_id"] == "L2-T01"
    assert "Contiguous" in qs[0]["options"][0]


def test_resolve_quiz_tags_from_note_index():
    qs = parse_smart_quiz_import(
        """
Question 1
Which is faster for large arrays?
A) Python loop
B) Vectorized NumPy
C) Recursion
D) Global variables
Answer: B
Tags: Vectorization
"""
    )
    resolved = resolve_quiz_tags(qs, note_text=NOTE_WITH_TOPICS)
    assert len(resolved) == 1
    assert resolved[0]["topic_id"] == "L2-T02"
    assert "Vectorization" in resolved[0]["concept"]


def test_header_tag_cascades_and_per_question_tag_wins():
    qs = parse_smart_quiz_import(
        """
topic_id: L2-T01

Question 1
Which memory layout do NumPy arrays use?
A) Contiguous homogeneous
B) Linked list
C) Hash map
D) Stack only
Answer: A

Question 2
Which call converts a list to an array?
topic_id: L2-T02
A) np.list()
B) np.array([1, 2])
C) array.new()
D) np.frame()
Answer: B
"""
    )
    assert [q["topic_id"] for q in qs] == ["L2-T01", "L2-T02"]
    # The cascaded header topic must not leak into a question with its own tag.
    assert "L2-T01" not in qs[1]["tags"]


def test_note_title_beats_keyword_guess_and_flags_unknown_tags():
    qs = parse_smart_quiz_import(
        """
topic_id: L2-T01

Question 1
Which numpy call builds an array from np.array inputs?
A) np.array([1, 2])
B) list()
C) dict()
D) set()
Answer: A
"""
    )
    assert qs[0]["concept"] == "NumPy"  # keyword guess before resolution

    resolved = resolve_quiz_tags(qs, note_text=NOTE_WITH_TOPICS)
    assert resolved[0]["concept"] == "NumPy arrays"  # note title wins
    assert resolved[0]["topic_known"] is True
    assert import_summary(resolved)["unknown_topics"] == []

    stale = resolve_quiz_tags(
        [{"question": "Q", "options": ["a", "b"], "topic_id": "L2-T99", "concept": "NumPy"}],
        note_text=NOTE_WITH_TOPICS,
    )
    assert stale[0]["topic_known"] is False
    assert import_summary(stale)["unknown_topics"] == ["L2-T99"]


def test_seed_deck_cards_covers_tagged_and_untagged(db):
    from backend.quiz import handler as quiz_handler

    user = db.query(User).first()
    items = parse_smart_quiz_import(
        """
Question 1
What memory layout do NumPy arrays use?
topic_id: L2-T01
A) Contiguous homogeneous
B) Linked list
C) Hash map
D) Stack only
Answer: A

Question 2
Which library reads CSV files?
A) numpy
B) pandas
C) os
D) sys
Answer: B
"""
    )
    assert [q["topic_id"] for q in items] == ["L2-T01", ""]

    deck = quiz_handler.save_deck(
        db,
        user=user,
        title="Imported Quiz",
        items=items,
        domain="study",
        topic="L2-T01",
    )
    assert deck["cards_seeded"] == 2

    cards = db.query(ReviewCard).filter(ReviewCard.user_id == user.id).all()
    assert len(cards) == 2
    topics = {c.topic for c in cards}
    assert "L2-T01" in topics


def test_import_summary_counts_topics():
    qs = [
        {"topic_id": "L2-T01"},
        {"topic_id": "L2-T01"},
        {"topic_id": "L2-T02"},
        {},
    ]
    summary = import_summary(qs)
    assert summary["total"] == 4
    assert summary["tagged"] == 3
    assert summary["untagged"] == 1
    assert {t["topic_id"] for t in summary["topics"]} == {"L2-T01", "L2-T02"}
