"""Tests for snapshot marker injection."""

from backend.transcripts.snapshots import inject_snapshot_images, next_snapshot_index


def test_inject_snapshot_images():
    raw = "Hello\n[SNAPSHOT 1]\nWorld"
    out = inject_snapshot_images(raw, "live_captions_test")
    assert "![Slide 1]" in out
    assert "/api/transcripts/snapshots/live_captions_test/1.png" in out


def test_next_snapshot_index_empty(tmp_path):
    p = tmp_path / "t.txt"
    assert next_snapshot_index(p) == 1
    p.write_text("[SNAPSHOT 2]\n", encoding="utf-8")
    assert next_snapshot_index(p) == 3
