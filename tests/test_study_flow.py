"""Tests for the unified Topic Study Flow."""

from fastapi.testclient import TestClient

from backend.main import app
from backend.models import User
from backend.db.session import get_db

def test_study_flow_endpoint(monkeypatch):
    client = TestClient(app)
    
    # Mock auth
    def override_get_current_user():
        return User(id=1, email="test@example.com")
        
    app.dependency_overrides["backend.core.auth.get_current_user"] = override_get_current_user
    
    # Mock LLM to avoid real calls
    monkeypatch.setattr("backend.corpus.grounded_notes.ollama_available", lambda *_: False)
    monkeypatch.setattr("backend.transcripts.study_intel.ollama_available", lambda *_: False)
    monkeypatch.setattr("backend.corpus.retrieve.corpus_available", lambda: True)
    monkeypatch.setattr("backend.corpus.grounded_notes.hybrid_retrieve", lambda *a, **k: [{"chunk_id": "c1", "content": "mock"}])
    monkeypatch.setattr("backend.corpus.handoff.ingest_lecture_handoff", lambda *a, **k: {"transcript_chunks": 5, "note_chunks": 3})
    
    from pathlib import Path
    from backend.paths import NOTES_DIR
    monkeypatch.setattr("backend.corpus.grounded_notes.generate_notes_from_file", lambda *a, **k: (NOTES_DIR / "dummy_note.md", "Mock content"))
    monkeypatch.setattr("backend.transcripts.study_flow.load_note_text", lambda *a, **k: "Mock note content")


    
    # We need a dummy transcript to exist
    from backend.paths import TRANSCRIPTS_DIR
    import os
    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    dummy_file = TRANSCRIPTS_DIR / "live_captions_test_dummy.txt"
    dummy_file.write_text("Dummy content for eigenvalues test.", encoding="utf-8")
    
    response = client.post(
        "/api/transcripts/study-flow/start",
        json={
            "topic": "eigenvalues",
            "transcript_file": "live_captions_test_dummy.txt",
            "folder_path": "study_test",
            "title": "Eigenvalues Test",
            "ingest_corpus": True,
            "quiz_count": 4,
            "start_quiz": False
        }
    )
    
    # Clean up dummy file
    if dummy_file.exists():
        os.remove(dummy_file)
        
    if response.status_code != 200:
        print("ERROR:", response.text)
    assert response.status_code == 200
    data = response.json()
    assert data["topic"] == "eigenvalues"
    assert "notes" in data["steps"]
    assert "quiz" in data["steps"]
    assert data["steps"]["corpus_handoff"]["note_chunks"] == 3
    assert data["steps"]["quiz"]["question_count"] == 4
    assert data["steps"]["quiz"]["session_id"] is not None
    assert "/lecture-notes?file=" in data["next_urls"]["notes"]
