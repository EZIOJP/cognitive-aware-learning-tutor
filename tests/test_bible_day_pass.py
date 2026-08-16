"""Weekly Bible day-pass quota."""

from backend.bible import store


def test_day_pass_requires_confirm(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "bible_dir", lambda: tmp_path)
    monkeypatch.setattr(store, "_day_key", lambda: "2026-07-22")
    monkeypatch.setattr(store, "_week_monday_key", lambda: "2026-07-20")

    try:
        store.request_day_pass(1, confirm="nope")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_day_pass_quota(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "bible_dir", lambda: tmp_path)
    monkeypatch.setattr(store, "DAY_PASSES_PER_WEEK", 2)

    days = ["2026-07-20", "2026-07-21", "2026-07-22"]

    def set_day(d: str):
        monkeypatch.setattr(store, "_day_key", lambda: d)
        monkeypatch.setattr(store, "_week_monday_key", lambda: "2026-07-20")

    set_day(days[0])
    out = store.request_day_pass(1, confirm="PASS")
    assert out["day_pass"] is True
    assert out["day_pass_status"]["used"] == 1
    assert out["day_pass_status"]["remaining"] == 1

    set_day(days[1])
    out2 = store.request_day_pass(1, confirm="PASS")
    assert out2["day_pass_status"]["remaining"] == 0

    set_day(days[2])
    try:
        store.request_day_pass(1, confirm="PASS")
        assert False, "expected quota error"
    except ValueError as e:
        assert "No day passes" in str(e)
