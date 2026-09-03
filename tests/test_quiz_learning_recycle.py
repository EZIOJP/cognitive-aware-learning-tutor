"""Learning-phase debt, recycle grades, Due path, ephemeral math regen."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.db.base import Base
from backend.models.review_card import ReviewCard
from backend.models.user import User
from backend.quiz import importance as imp
from backend.quiz import review_cards as rc
from backend.quiz import srs as srs_mod


def test_recycle_correct_does_not_reschedule():
    due = datetime.now(UTC) + timedelta(days=4)
    state = srs_mod.SrsState(
        mastery=2,
        owes_corrects=2,
        interval_days=4,
        due_date=due,
        stability=8.0,
        difficulty=5.0,
    )
    nxt = srs_mod.apply_recycle_answer(state, correct=True)
    assert nxt.owes_corrects == 1
    assert nxt.mastery == 3
    assert nxt.interval_days == 4
    assert nxt.due_date == due
    assert nxt.stability == 8.0


def test_fail_while_owing_resets_to_two_never_three():
    state = srs_mod.SrsState(mastery=1, owes_corrects=1)
    nxt = srs_mod.apply_recycle_answer(state, correct=False)
    assert nxt.owes_corrects == 2


def test_is_due_when_owes_even_if_future():
    state = srs_mod.SrsState(
        mastery=5,
        owes_corrects=1,
        due_date=datetime.now(UTC) + timedelta(days=30),
    )
    assert srs_mod.is_due(state) is True


def test_entry_fail_sets_owes_two_and_full_grade(tmp_path: Path):
    path = tmp_path / "tag_importance.json"
    store = imp.empty_store()
    state = srs_mod.SrsState(mastery=3)
    nxt = imp.apply_learning_grade(
        state,
        correct=False,
        payload={"tags": ["MT1-T07"]},
        session_tag="MT1-T07",
        store=store,
    )
    assert nxt.owes_corrects == 2
    assert nxt.due_date is not None
    assert nxt.interval_days >= 1
    assert nxt.mastery == 1  # 3 - 2


def test_owing_correct_skips_fsrs():
    due = datetime.now(UTC) + timedelta(days=6)
    state = srs_mod.SrsState(
        mastery=6,
        owes_corrects=2,
        interval_days=6,
        due_date=due,
        stability=12.0,
    )
    nxt = imp.apply_learning_grade(state, correct=True, payload={"tags": ["X"]})
    assert nxt.owes_corrects == 1
    assert nxt.interval_days == 6
    assert nxt.stability == 12.0
    assert nxt.mastery == 7


def test_due_submit_with_debt_is_recycle():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    user = User(id=1, username="t", password_hash="x")
    db.add(user)
    db.commit()
    due = datetime.now(UTC) + timedelta(days=10)
    card = rc.upsert_review_card(
        db,
        user_id=1,
        domain="study",
        item_id="q1",
        label="Q",
        payload={"tags": ["MT1-T07"], "question": "x", "options": ["a"], "answer_index": 0},
        correct=True,
        topic="MT1-T07",
    )
    st = srs_mod.srs_from_metadata(__import__("json").loads(card.srs_json))
    st.owes_corrects = 2
    st.due_date = due
    st.interval_days = 10
    st.stability = 9.0
    card.srs_json = __import__("json").dumps(srs_mod.srs_to_metadata(st))
    db.commit()
    assert any(c.id == card.id for c in rc.list_due_cards(db, user_id=1))
    card2 = rc.upsert_review_card(
        db,
        user_id=1,
        domain="study",
        item_id="q1",
        label="Q",
        payload={"tags": ["MT1-T07"], "question": "x", "options": ["a"], "answer_index": 0},
        correct=True,
        topic="MT1-T07",
    )
    st2 = srs_mod.srs_from_metadata(__import__("json").loads(card2.srs_json))
    assert st2.owes_corrects == 1
    assert st2.interval_days == 10
    db.close()


def test_ephemeral_math_recycle_does_not_write_bank(tmp_path: Path, monkeypatch):
    bank = tmp_path / "questions" / "math"
    bank.mkdir(parents=True)
    before = list(bank.rglob("*"))
    monkeypatch.setattr(
        "backend.quiz.math_generators.list_recipes",
        lambda: [MagicMock(gen_id=1, note_topic_id="MT1-T01")],
    )
    monkeypatch.setattr(
        "backend.quiz.math_generators.generate_one",
        lambda recipe: ("2+2?", "4"),
    )
    item = {"kind": "math", "gen_id": 1, "prompt": "1+1?", "expected_answer": "2"}
    out = imp.ephemeral_math_recycle(item)
    assert out["prompt"] == "2+2?"
    assert out["expected_answer"] == "4"
    assert list(bank.rglob("*")) == before
    assert out.get("_ephemeral") is True
