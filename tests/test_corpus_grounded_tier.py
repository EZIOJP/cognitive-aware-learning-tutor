"""Corpus grounded notes — llm_tier passthrough from request body."""

from __future__ import annotations

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from backend.core.auth import get_current_user
from backend.main import app
from backend.models import User
from backend.paths import NOTES_DIR, TRANSCRIPTS_DIR


def test_grounded_notes_passes_llm_tier(monkeypatch):
    client = TestClient(app)

    def override_get_current_user():
        return User(id=1, username="test", password_hash="hash")

    app.dependency_overrides[get_current_user] = override_get_current_user

    captured: dict = {}

    def fake_generate_grounded_notes(**kwargs):
        captured.update(kwargs)
        note_path = NOTES_DIR / "tier_test.md"
        note_path.parent.mkdir(parents=True, exist_ok=True)
        note_path.write_text("# Tier test\n", encoding="utf-8")
        return {
            "mode": "grounded",
            "notes_path": str(note_path),
            "markdown": "# Tier test\n",
            "chunk_count": 1,
        }

    monkeypatch.setattr("backend.corpus.router.get_settings", lambda: MagicMock(corpus_grounded_notes=True))
    monkeypatch.setattr("backend.corpus.grounded_notes.generate_grounded_notes", fake_generate_grounded_notes)
    monkeypatch.setattr(
        "backend.transcripts.router._save_generated_note",
        lambda *a, **k: None,
    )

    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    dummy = TRANSCRIPTS_DIR / "tier_test_transcript.txt"
    dummy.write_text("Eigenvalues and eigenvectors.", encoding="utf-8")

    try:
        response = client.post(
            "/api/corpus/generate-notes-grounded",
            json={
                "transcript_file": "tier_test_transcript.txt",
                "topic": "linear algebra",
                "title": "Tier Test",
                "folder_path": "",
                "llm_tier": "heavy",
            },
        )
    finally:
        app.dependency_overrides.clear()
        if dummy.exists():
            dummy.unlink()
        note_file = NOTES_DIR / "tier_test.md"
        if note_file.exists():
            note_file.unlink()

    assert response.status_code == 200, response.text
    assert captured.get("llm_tier") == "heavy"
