"""Bible game-bank math (no DB)."""

from backend.bible import store


def test_bible_bank_chunks(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "bible_dir", lambda: tmp_path)
    monkeypatch.setattr(store, "_day_key", lambda: "2026-07-22")

    assert store.game_bank_remaining_seconds(1) == 0
    day = store.load_day(1)
    day["bible_seconds"] = 30 * 60
    store.save_day(1, day)
    assert store.game_bank_remaining_seconds(1) == 30 * 60

    left = store.consume_game_seconds(1, 10 * 60)
    assert left == 20 * 60

    day = store.load_day(1)
    day["bible_seconds"] = 60 * 60
    store.save_day(1, day)
    # earned 60m, consumed 10m → 50m left
    assert store.game_bank_remaining_seconds(1) == 50 * 60


def test_taskmgr_does_not_drain_bank():
    from backend.behavior.distraction_gate import is_game_bank_drain_target, should_hard_block

    policy = {"hard_block_enabled": True, "hard_block_gaming": True, "hard_block_exes": []}
    assert should_hard_block("taskmgr.exe", None, policy)
    assert not is_game_bank_drain_target("taskmgr.exe", None, policy)
    assert is_game_bank_drain_target("steam.exe", "Gaming", policy)
