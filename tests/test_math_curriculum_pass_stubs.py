from pathlib import Path

from backend.math.curriculum_pass.stubs import ensure_note_stubs
from backend.transcripts.note_topics import parse_note_topics


def test_stub_creates_heading_idempotent(tmp_path: Path):
    stats = ensure_note_stubs([("MT1-T07", "Time & work")], notes_dir=tmp_path)
    assert stats["stubs_created"] == 1
    path = tmp_path / "MT1_aptitude_interview_notes.md"
    text = path.read_text(encoding="utf-8")
    assert "## `MT1-T07` — Time & work" in text
    topics = parse_note_topics(text, min_body_chars=0)
    assert any(t.topic_id == "MT1-T07" for t in topics)
    stats2 = ensure_note_stubs([("MT1-T07", "Time & work")], notes_dir=tmp_path)
    assert stats2["stubs_created"] == 0
    path.write_text(
        text.replace("TODO: fill notes", "Real notes about work rates."),
        encoding="utf-8",
    )
    ensure_note_stubs([("MT1-T07", "Time & work")], notes_dir=tmp_path)
    assert "Real notes about work rates." in path.read_text(encoding="utf-8")
