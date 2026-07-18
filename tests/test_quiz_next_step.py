"""next_step priority helpers."""

from unittest.mock import MagicMock, patch

from backend.quiz import next_step as ns
from backend.quiz.next_step import compute_next_step


def test_next_step_sign_in_without_user():
    db = MagicMock()
    step = compute_next_step(db, user_id=None)
    assert step["action"] == "sign_in"


def test_next_step_review_due_wins():
    db = MagicMock()
    card = MagicMock()
    card.domain = "vocab"
    card.srs_json = "{}"
    db.query.return_value.filter.return_value.all.return_value = [card]

    with patch.object(ns.srs_mod, "is_due", return_value=True):
        with patch.object(ns.srs_mod, "srs_from_metadata", return_value=MagicMock()):
            step = compute_next_step(db, user_id=1)
    assert step["action"] == "review_due"
    assert step["due_count"] == 1
