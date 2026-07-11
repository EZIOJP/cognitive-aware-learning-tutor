"""Smoke: grounding_status + 409 mtime (mocked LLM — no live generate)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch
from urllib.parse import quote

from fastapi.testclient import TestClient

from backend.core.auth import get_current_user
from backend.main import app
from backend.models import User
from backend.paths import NOTES_DIR, TRANSCRIPTS_DIR
from backend.transcripts.note_generation import resolve_grounding


def main() -> None:
    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    smoke = TRANSCRIPTS_DIR / "_smoke_grounding_thin.txt"
    smoke.write_text("Unicorn calculus logistics only.\n", encoding="utf-8")
    note_path = NOTES_DIR / "_smoke_grounding_thin.md"
    note_path.write_text("# Smoke\n\nTranscript-only note.\n", encoding="utf-8")

    def override():
        return User(id=1, username="smoke", password_hash="x")

    app.dependency_overrides[get_current_user] = override
    client = TestClient(app)

    st, reason = resolve_grounding("legacy", {})
    assert st == "degraded"
    print("OK degraded legacy", reason)

    st, reason = resolve_grounding(
        "hybrid",
        {"citations": [], "chunk_count": 0, "chunk_meta": [{"hit_count": 0}]},
    )
    assert st == "degraded" and reason == "no_textbook_chunks_retrieved"
    print("OK degraded zero textbook hits")

    st, reason = resolve_grounding("hybrid", {"citations": ["tb-1"], "chunk_count": 2})
    assert st == "grounded" and reason is None
    print("OK grounded with citations")

    def fake_degraded(**kwargs):
        rag = {
            "notes_path": str(note_path),
            "markdown": note_path.read_text(encoding="utf-8"),
            "mode": "legacy",
            "grounding_status": "degraded",
            "grounding_reason": "no_textbook_chunks_retrieved",
            "citations": [],
        }
        return note_path, rag["markdown"], "legacy", rag

    def fake_grounded(**kwargs):
        rag = {
            "notes_path": str(note_path),
            "markdown": note_path.read_text(encoding="utf-8"),
            "mode": "hybrid",
            "grounding_status": "grounded",
            "grounding_reason": None,
            "citations": ["tb-1"],
        }
        return note_path, rag["markdown"], "hybrid", rag

    with patch(
        "backend.transcripts.note_generation.generate_notes_unified",
        side_effect=fake_degraded,
    ):
        res = client.post(
            "/api/transcripts/notes/generate",
            json={"transcript_file": smoke.name, "title": "Smoke Thin", "force_legacy": True},
        )
    assert res.status_code == 200, res.json()
    data = res.json()
    assert data.get("grounding_status") == "degraded", data
    print("OK API degraded", data.get("grounding_reason"))

    with patch(
        "backend.transcripts.note_generation.generate_notes_unified",
        side_effect=fake_grounded,
    ):
        res2 = client.post(
            "/api/transcripts/notes/generate",
            json={"transcript_file": smoke.name, "title": "Smoke Grounded"},
        )
    assert res2.status_code == 200, res2.json()
    assert res2.json().get("grounding_status") == "grounded"
    print("OK API grounded")

    rel = note_path.name
    enc = "/".join(quote(p) for p in rel.split("/"))
    g = client.get(f"/api/transcripts/library/files/{enc}/content")
    assert g.status_code == 200
    body = g.json()
    assert "mtime" in body
    bad = client.put(
        f"/api/transcripts/library/files/{enc}/content",
        json={"content": body["content"], "expected_mtime": float(body["mtime"]) - 50},
    )
    assert bad.status_code == 409
    print("OK 409 conflict", bad.json().get("detail"))

    page = Path("src/pages/study/LectureNotesPage.tsx").read_text(encoding="utf-8")
    assert "textbook grounding unavailable" in page
    assert "NoteConflictError" in page
    assert "changed elsewhere" in page
    print("OK FE banner + conflict UX strings")

    print("SMOKE_OK")
    app.dependency_overrides.clear()


if __name__ == "__main__":
    main()
