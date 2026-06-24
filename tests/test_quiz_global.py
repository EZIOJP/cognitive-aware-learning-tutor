"""Global quiz handler — study notes and code drills."""

from unittest.mock import MagicMock

import pytest

from backend.quiz import handler


def _user(user_id: int = 1):
    u = MagicMock()
    u.id = user_id
    return u


def test_start_study_quiz_from_note_questions():
    db = MagicMock()
    questions = [
        {
            "id": "q1",
            "question": "What is NumPy?",
            "options": ["A library", "A snake", "A database", "A OS"],
            "answer_index": 0,
            "explanation": "Numeric Python",
        }
    ]
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(handler, "create_global_session", lambda *a, **k: "sess-1")
        mp.setattr(
            handler,
            "load_global_session",
            lambda *a, **k: None,
        )
        result = handler.start_session(
            db,
            user=_user(),
            domain="study",
            config={
                "questions": questions,
                "drills": [],
                "note_path": "lecture one/notes.md",
                "topic": "NumPy",
            },
        )
    assert result["session_id"] == "sess-1"
    assert result["domain"] == "study"
    assert result["question"]["format"] == "mcq"
    assert result["question"]["prompt"] == "What is NumPy?"
    assert len(result["question"]["options"]) == 4


def test_submit_study_mcq_correct():
    db = MagicMock()
    items = [
        {
            "kind": "mcq",
            "id": "q1",
            "question": "Pick A",
            "options": ["Alpha", "Beta"],
            "answer_index": 0,
        }
    ]
    sess = {
        "row": MagicMock(),
        "domain": "study",
        "payload": {"items": items, "note_path": "notes/a.md", "topic": "Test"},
        "index": 0,
        "attempts": [],
    }
    node = MagicMock()
    node.metadata_json = "{}"
    node.id = 42

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(handler, "get_quiz_session", lambda *a, **k: None)
        mp.setattr(handler, "load_global_session", lambda *a, **k: sess)
        mp.setattr(handler, "upsert_node", lambda *a, **k: node)
        mp.setattr(handler, "log_observation", lambda *a, **k: None)
        mp.setattr(handler, "save_global_session", lambda *a, **k: None)
        mp.setattr(handler, "_record_review_card", lambda *a, **k: 3)

        result = handler.submit_answer(
            db,
            user=_user(),
            session_id="sess-1",
            item_id="q1",
            response="Alpha",
        )

    assert result["correct"] is True
    assert result["complete"] is True
    assert result["next_question"] is None


def test_generate_quiz_items_template_without_llm(monkeypatch):
    from backend.transcripts.study_intel import generate_quiz_items

    monkeypatch.setattr("backend.transcripts.study_intel.ollama_available", lambda *_: False)
    result = generate_quiz_items(["## NumPy arrays\n- ndarray basics"], count=3, topic="NumPy")
    assert result["source"] == "template"
    assert len(result["questions"]) == 3
    assert result["questions"][0]["options"]
