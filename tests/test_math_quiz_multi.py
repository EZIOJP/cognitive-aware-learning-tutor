"""SymPy answer equivalence + multi-question math quiz start."""

from unittest.mock import MagicMock

import pytest

from backend.math.answer_grade import answers_equivalent
from backend.quiz import handler


@pytest.mark.parametrize(
    "expected,user,ok",
    [
        ("1/2", "0.5", True),
        ("1/2", "50%", True),
        ("x+1", "1+x", True),
        ("4", "4", True),
        ("4", "5", False),
        ("2/4", "1/2", True),
        ("", "1", False),
        ("1", "not-a-number!!!", False),
    ],
)
def test_answers_equivalent(expected, user, ok):
    assert answers_equivalent(expected, user) is ok


def _user(user_id: int = 1):
    u = MagicMock()
    u.id = user_id
    return u


def test_start_math_builds_items_list():
    db = MagicMock()
    problems = [
        {
            "question_id": 1,
            "prompt": "2+2",
            "expected_answer": "4",
            "topic": "Arithmetic",
            "generated_id": "g1",
            "explanation": "add",
        },
        {
            "question_id": 2,
            "prompt": "3+3",
            "expected_answer": "6",
            "topic": "Arithmetic",
            "generated_id": "g2",
            "explanation": "add",
        },
        {
            "question_id": 3,
            "prompt": "4+4",
            "expected_answer": "8",
            "topic": "Arithmetic",
            "generated_id": "g3",
            "explanation": "add",
        },
    ]
    captured: dict = {}

    def _create(*_a, **k):
        captured["payload"] = k.get("payload")
        return "math-sess"

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(handler, "pick_n_from_bank", lambda *a, **k: problems)
        mp.setattr(handler, "create_global_session", _create)
        result = handler.start_session(
            db,
            user=_user(),
            domain="math",
            config={"topic": "Arithmetic", "count": 3},
        )

    assert result["session_id"] == "math-sess"
    assert result["domain"] == "math"
    items = captured["payload"]["items"]
    assert len(items) == 3
    assert all(it["kind"] == "math" for it in items)
    assert result["question"]["format"] == "free_text"
    assert "2+2" in result["question"]["prompt"]


def test_submit_math_item_advances_to_next():
    db = MagicMock()
    items = [
        {
            "kind": "math",
            "id": "1",
            "prompt": "2+2",
            "expected_answer": "4",
            "topic": "Arithmetic",
            "question_id": 1,
        },
        {
            "kind": "math",
            "id": "2",
            "prompt": "3+3",
            "expected_answer": "6",
            "topic": "Arithmetic",
            "question_id": 2,
        },
    ]
    sess = {
        "row": MagicMock(),
        "domain": "math",
        "payload": {"items": items, "topic": "Arithmetic"},
        "index": 0,
        "attempts": [],
    }
    node = MagicMock()
    node.metadata_json = "{}"
    node.id = 7

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(handler, "get_quiz_session", lambda *a, **k: None)
        mp.setattr(handler, "load_global_session", lambda *a, **k: sess)
        mp.setattr(handler, "upsert_node", lambda *a, **k: node)
        mp.setattr(handler, "log_observation", lambda *a, **k: None)
        mp.setattr(handler, "save_global_session", lambda *a, **k: None)
        mp.setattr(handler, "_record_review_card", lambda *a, **k: (2, 0))
        out = handler.submit_answer(
            db,
            user=_user(),
            session_id="s1",
            item_id="1",
            response="4",
            time_taken_ms=100,
        )

    assert out["correct"] is True
    assert out["complete"] is False
    assert out["next_question"] is not None
    assert sess["index"] == 1
