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


def test_start_study_quiz_auto_generate_from_note_path():
    db = MagicMock()
    questions = [
        {
            "id": "q1",
            "question": "What is an eigenvalue?",
            "options": ["Scalar", "Vector", "Matrix", "Tensor"],
            "answer_index": 0,
        }
    ]
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            handler,
            "_auto_generate_study_questions",
            lambda *a, **k: questions,
        )
        mp.setattr(handler, "create_global_session", lambda *a, **k: "sess-auto")
        result = handler.start_session(
            db,
            user=_user(),
            domain="study",
            config={"note_path": "study_test/eigenvalues.md", "topic": "Eigenvalues"},
        )
    assert result["session_id"] == "sess-auto"
    assert result["question"]["prompt"] == "What is an eigenvalue?"


def test_start_study_quiz_replaces_bland_heading_questions():
    db = MagicMock()
    replacement = [
        {
            "id": "q1",
            "question": "Why are NumPy arrays faster than Python lists?",
            "options": ["Contiguous homogeneous memory", "One-based indexing", "Mixed objects", "Text conversion"],
            "answer_index": 0,
        }
    ]
    bland = {
        "id": "old",
        "question": "Which statement best matches the note section NumPy?",
        "options": ["It relates to: NumPy", "Pandas", "EDA", "Indexing"],
        "answer_index": 0,
    }
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(handler, "_auto_generate_study_questions", lambda *a, **k: replacement)
        mp.setattr(handler, "create_global_session", lambda *a, **k: "sess-replaced")
        result = handler.start_session(
            db,
            user=_user(),
            domain="study",
            config={"questions": [bland], "note_path": "lecture_2/numpy.md"},
        )
    assert result["question"]["prompt"] == replacement[0]["question"]


def test_start_study_quiz_auto_generate_passes_llm_tier():
    db = MagicMock()
    captured: dict = {}

    def fake_auto(*_a, **kwargs):
        captured.update(kwargs)
        return [
            {
                "id": "q1",
                "question": "Why are NumPy arrays faster than lists?",
                "options": ["Contiguous memory", "One-based index", "Text storage", "Slower loops"],
                "answer_index": 0,
            }
        ]

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(handler, "_auto_generate_study_questions", fake_auto)
        mp.setattr(handler, "create_global_session", lambda *a, **k: "sess-llm")
        result = handler.start_session(
            db,
            user=_user(),
            domain="study",
            config={
                "note_path": "lecture_2/numpy.md",
                "topic": "NumPy",
                "llm_tier": "medium",
                "llm_provider": "lmstudio",
                "llm_base_url": "http://127.0.0.1:1234",
                "llm_model": "test-model",
                "confirm_heavy_budget": False,
            },
        )
    assert result["session_id"] == "sess-llm"
    assert captured.get("llm_tier") == "medium"
    assert isinstance(captured.get("llm"), dict)
    assert captured["llm"]["llm_provider"] == "lmstudio"


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
        mp.setattr(handler, "_record_review_card", lambda *a, **k: (3, 0))

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
    assert result.get("requeued") is False


def test_submit_study_mcq_wrong_shows_concept_and_requeues():
    db = MagicMock()
    items = [
        {
            "kind": "mcq",
            "id": "q1",
            "question": "Pick A",
            "options": ["Alpha", "Beta"],
            "answer_index": 0,
            "concept": "Fancy indexing",
            "explanation": "Alpha is right because …",
        },
        {
            "kind": "mcq",
            "id": "q2",
            "question": "Pick B",
            "options": ["X", "Y"],
            "answer_index": 1,
        },
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
        mp.setattr(handler, "_record_review_card", lambda *a, **k: (3, 0))

        result = handler.submit_answer(
            db,
            user=_user(),
            session_id="sess-1",
            item_id="q1",
            response="Beta",
        )

    assert result["correct"] is False
    assert "Topic to review: Fancy indexing" in result["feedback"]
    assert result["requeued"] is True
    assert result["complete"] is False
    assert result["next_question"] is not None
    assert len(sess["payload"]["items"]) == 3
    assert any(it.get("_requeued") for it in sess["payload"]["items"])


def test_generate_quiz_items_template_without_llm(monkeypatch):
    from backend.transcripts.study_intel import generate_quiz_items

    monkeypatch.setattr("backend.transcripts.study_intel.ollama_available", lambda *_: False)
    note = (
        "## NumPy arrays\n"
        "NumPy arrays are faster than Python lists because contiguous homogeneous memory enables vectorized ops.\n"
        "Indexing returns np.int64, not a plain Python int.\n"
        "Out-of-bounds direct indexing raises IndexError.\n"
    )
    result = generate_quiz_items([note], count=3, topic="NumPy")
    assert result["source"] == "extractive"
    assert len(result["questions"]) == 3
    assert result["questions"][0]["options"]
    joined = " ".join(q["question"] for q in result["questions"])
    assert "completes this claim" not in joined.casefold()
    assert any(word in joined for word in ("faster", "IndexError", "np.int64", "NumPy", "index"))
