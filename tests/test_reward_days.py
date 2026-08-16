"""Reward-day credit accounting stays stackable and is safe to claim once."""

from __future__ import annotations


def test_four_qualifying_days_bank_one_reward_and_claim(monkeypatch, tmp_path):
    from backend.behavior import reward_days

    day = {"reward_day": False}
    monkeypatch.setattr(reward_days, "bible_dir", lambda: tmp_path)
    monkeypatch.setattr(reward_days.bible_store, "load_day", lambda _uid: dict(day))

    def save_day(_uid, value):
        day.clear()
        day.update(value)

    monkeypatch.setattr(reward_days.bible_store, "save_day", save_day)
    monkeypatch.setattr(reward_days, "_today", lambda: "2026-08-15")

    for i in range(4):
        monkeypatch.setattr(reward_days, "_today", lambda i=i: f"2026-08-{15 + i:02d}")
        status = reward_days.record_qualifying_day(7, qualified=True)

    assert status["available"] == 1
    assert status["qualifying_days"] == 4

    monkeypatch.setattr(reward_days, "_today", lambda: "2026-08-20")
    claimed = reward_days.claim_reward_day(7, confirm="REWARD", already_unlocked=False)
    assert claimed["ok"] is True
    assert claimed["available"] == 0
    assert day["reward_day"] is True


def test_reward_day_rejects_unearned_or_already_unlocked(monkeypatch, tmp_path):
    from backend.behavior import reward_days

    monkeypatch.setattr(reward_days, "bible_dir", lambda: tmp_path)
    monkeypatch.setattr(reward_days.bible_store, "load_day", lambda _uid: {"reward_day": False})
    monkeypatch.setattr(reward_days, "_today", lambda: "2026-08-15")

    try:
        reward_days.claim_reward_day(7, confirm="REWARD", already_unlocked=False)
    except ValueError as exc:
        assert "Complete 4" in str(exc)
    else:
        raise AssertionError("expected unearned reward-day claim to fail")

    try:
        reward_days.claim_reward_day(7, confirm="REWARD", already_unlocked=True)
    except ValueError as exc:
        assert "already unlocked" in str(exc)
    else:
        raise AssertionError("expected already-unlocked claim to fail")


def test_grant_credits_banks_and_claimable(monkeypatch, tmp_path):
    from backend.behavior import reward_days

    day = {"reward_day": False}
    monkeypatch.setattr(reward_days, "bible_dir", lambda: tmp_path)
    monkeypatch.setattr(reward_days.bible_store, "load_day", lambda _uid: dict(day))

    def save_day(_uid, value):
        day.clear()
        day.update(value)

    monkeypatch.setattr(reward_days.bible_store, "save_day", save_day)
    monkeypatch.setattr(reward_days, "_today", lambda: "2026-08-15")

    granted = reward_days.grant_credits(7, 3)
    assert granted["available"] == 3
    assert granted["granted"] == 3

    claimed = reward_days.claim_reward_day(7, confirm="REWARD", already_unlocked=False)
    assert claimed["ok"] is True
    assert claimed["available"] == 2
    assert day["reward_day"] is True
