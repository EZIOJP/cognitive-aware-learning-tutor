"""Tests for daily devotion blocks (Proverbs/Psalms + hymns)."""

from backend.bible import devotion


def test_afternoon_proverbs_with_prayer():
    p = devotion.resolve_afternoon_reading("2026-09-01")
    p2 = devotion.resolve_afternoon_reading("2026-09-02")
    assert p["book"] == "Proverbs"
    assert p2["book"] == "Proverbs"
    assert "prayer" in p
    assert "wisdom" in p["prayer"].lower()
    assert "healing" in p["prayer"].lower()
    assert "job" in p["prayer"].lower() or "labor" in p["prayer"].lower()


def test_evening_psalms_and_worship():
    eve = devotion.resolve_evening_reading("2026-09-01")
    assert eve["book"] == "Psalms"
    assert eve["chapter"] >= 1
    assert eve["worship_title"]
    assert eve["hymn_id"]


def test_evening_hymn_rotation():
    h1 = devotion.resolve_evening_hymn("2026-09-01")
    h2 = devotion.resolve_evening_hymn("2026-09-02")
    assert h1["title"]
    assert h1["opening"]
    assert len(devotion.list_praise_hymns()) >= 10


def test_morning_has_lords_prayer():
    m = devotion.morning_devotion()
    assert "Father" in m["lords_prayer"]
    assert m["note"]


def test_mark_devotion_afternoon(tmp_path, monkeypatch):
    from backend.bible import store as bible_store

    monkeypatch.setattr(bible_store, "bible_dir", lambda: tmp_path)
    tmp_path.mkdir(parents=True, exist_ok=True)
    uid = 42
    out = bible_store.mark_devotion_done(uid, "afternoon", done=True)
    assert out["afternoon"]["done"] is True
    again = bible_store.devotion_summary(uid)
    assert again["afternoon"]["done"] is True


def test_save_devotion_notes(tmp_path, monkeypatch):
    from backend.bible import store as bible_store

    monkeypatch.setattr(bible_store, "bible_dir", lambda: tmp_path)
    tmp_path.mkdir(parents=True, exist_ok=True)
    uid = 7
    out = bible_store.save_devotion_notes(uid, "evening", "Psalm 23 comforted me.")
    assert "comforted" in out["evening"]["notes"]
