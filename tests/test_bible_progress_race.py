"""Bible day/reader merge must not lose ticks to heartbeat races."""

from __future__ import annotations

from pathlib import Path

from backend.bible import store as s


def test_save_day_merges_chapters(tmp_path, monkeypatch):
    monkeypatch.setattr(s, "bible_dir", lambda: Path(tmp_path))
    monkeypatch.setattr(s, "_day_key", lambda: "2099-01-01")
    uid = 99
    day = s._empty_day()
    day["chapters_completed"] = ["Genesis|18"]
    day["assigned_book"] = "Genesis"
    day["assigned_chapter"] = 18
    day["assigned_key"] = "Genesis|18"
    s.save_day(uid, day)

    # Stale heartbeat view (no completion) must not wipe the tick
    stale = s._empty_day()
    stale["bible_seconds"] = 50
    stale["assigned_book"] = "Genesis"
    stale["assigned_chapter"] = 18
    stale["assigned_key"] = "Genesis|18"
    s.save_day(uid, stale)

    loaded = s.load_day(uid)
    assert "Genesis|18" in loaded["chapters_completed"]
    assert int(loaded["bible_seconds"]) >= 50


def test_patch_reader_keeps_completed(tmp_path, monkeypatch):
    monkeypatch.setattr(s, "bible_dir", lambda: Path(tmp_path))
    uid = 99
    s._write_json(
        s._reader_path(uid),
        {"completed_chapters": ["Genesis|1", "Genesis|2"], "plan_cursor": 2},
    )
    s._patch_reader(uid, last_book="Genesis", last_chapter=2)
    reader = s._read_json(s._reader_path(uid), {})
    assert "Genesis|1" in reader["completed_chapters"]
    assert "Genesis|2" in reader["completed_chapters"]
    assert reader["last_book"] == "Genesis"
