"""Tests for the unified Topic Study Flow."""

from fastapi.testclient import TestClient

from backend.core.auth import get_current_user
from backend.main import app
from backend.models import User


def test_study_flow_endpoint(monkeypatch):
    client = TestClient(app)

    def override_get_current_user():
        return User(id=1, username="test", password_hash="hash")

    app.dependency_overrides[get_current_user] = override_get_current_user

    monkeypatch.setattr(
        "backend.transcripts.study_flow.get_settings",
        lambda: type("S", (), {"corpus_grounded_notes": False})(),
    )

    from backend.paths import NOTES_DIR, TRANSCRIPTS_DIR

    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    dummy_file = TRANSCRIPTS_DIR / "live_captions_test_dummy.txt"
    dummy_file.write_text("Dummy content for eigenvalues test.", encoding="utf-8")
    note_path = NOTES_DIR / "study_test" / "eigenvalues_test.md"
    note_path.parent.mkdir(parents=True, exist_ok=True)
    note_path.write_text("# Eigenvalues\n\n- Mock content\n", encoding="utf-8")

    monkeypatch.setattr(
        "backend.transcripts.note_generation.generate_notes_unified",
        lambda **_k: (
            note_path,
            note_path.read_text(encoding="utf-8"),
            "legacy",
            {
                "grounding_status": "degraded",
                "grounding_reason": "corpus_rag_disabled",
                "mode": "legacy",
            },
        ),
    )
    monkeypatch.setattr(
        "backend.transcripts.study_flow.load_note_text",
        lambda *_a, **_k: "Mock note content about eigenvalues",
    )
    monkeypatch.setattr(
        "backend.transcripts.study_flow.generate_quiz_items",
        lambda *_a, **_k: {
            "questions": [
                {"question": "Q1?", "answer": "A1", "type": "short"},
                {"question": "Q2?", "answer": "A2", "type": "short"},
                {"question": "Q3?", "answer": "A3", "type": "short"},
                {"question": "Q4?", "answer": "A4", "type": "short"},
            ]
        },
    )
    monkeypatch.setattr(
        "backend.transcripts.study_flow.start_session",
        lambda *_a, **_k: {"session_id": "sess-test-1"},
    )

    try:
        response = client.post(
            "/api/transcripts/study-flow/start",
            json={
                "topic": "eigenvalues",
                "transcript_file": "live_captions_test_dummy.txt",
                "folder_path": "study_test",
                "title": "Eigenvalues Test",
                "ingest_corpus": False,
                "quiz_count": 4,
                "start_quiz": False,
            },
        )
    finally:
        if dummy_file.exists():
            dummy_file.unlink()
        app.dependency_overrides.pop(get_current_user, None)

    if response.status_code != 200:
        print("ERROR:", response.text)
    assert response.status_code == 200
    data = response.json()
    assert data["topic"] == "eigenvalues"
    assert "notes" in data["steps"]
    assert "quiz" in data["steps"]
    assert data["steps"]["notes"]["mode"] == "legacy"
    assert data["steps"]["quiz"]["question_count"] == 4
    assert data["steps"]["quiz"]["session_id"] == "sess-test-1"
    assert "/lecture-notes?file=" in data["next_urls"]["notes"]
