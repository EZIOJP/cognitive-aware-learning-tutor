"""Reward-day credit accounting goes through the enforcer gateway."""

from __future__ import annotations


def test_four_qualifying_days_bank_one_reward_and_claim(monkeypatch):
    from backend.behavior import reward_days

    day = {"reward_day": False}
    calls = []
    state = {"qualified": 0, "used": 0, "granted": 0, "reward_active": False}

    def fake_call(op, payload=None, **kw):
        calls.append((op, payload))
        if op == "reward.mark_qualified":
            state["qualified"] += 1
            return {"ok": True, "qualified_days": state["qualified"]}
        if op == "day.mark_event":
            return {"ok": True, "credited_seconds": 0}
        if op == "reward.status":
            q = state["qualified"]
            earned = q // 4
            available = max(0, earned + state["granted"] - state["used"])
            return {
                "ok": True,
                "qualified_days": q,
                "reward_earned": earned,
                "reward_granted": state["granted"],
                "reward_spent": state["used"],
                "reward_available": available,
                "days_to_next_reward": 4 - (q % 4),
            }
        if op == "reward.claim":
            if state["qualified"] // 4 + state["granted"] - state["used"] <= 0:
                return {"ok": False, "error": "no_reward_available"}
            state["used"] += 1
            state["reward_active"] = True
            return {"ok": True}
        return {"ok": True}

    monkeypatch.setattr("backend.behavior.enforcer_gateway.gateway_call", fake_call)
    monkeypatch.setattr(reward_days.bible_store, "load_day", lambda _uid: dict(day))

    def save_day(_uid, value):
        day.clear()
        day.update(value)

    monkeypatch.setattr(reward_days.bible_store, "save_day", save_day)

    for _ in range(4):
        status = reward_days.record_qualifying_day(7, qualified=True)

    assert status["available"] == 1
    assert status["qualifying_days"] == 4

    claimed = reward_days.claim_reward_day(7, confirm="REWARD", already_unlocked=False)
    assert claimed["ok"] is True
    assert claimed["available"] == 0
    assert day["reward_day"] is True
    assert ("reward.claim", {"confirm": "REWARD"}) in calls


def test_reward_day_rejects_unearned_or_already_unlocked(monkeypatch):
    from backend.behavior import reward_days

    monkeypatch.setattr(reward_days.bible_store, "load_day", lambda _uid: {"reward_day": False})

    def fake_call(op, payload=None, **kw):
        if op == "reward.claim":
            return {"ok": False, "error": "no_reward_available"}
        if op == "reward.status":
            return {
                "ok": True,
                "qualified_days": 0,
                "reward_earned": 0,
                "reward_granted": 0,
                "reward_spent": 0,
                "reward_available": 0,
                "days_to_next_reward": 4,
            }
        return {"ok": True}

    monkeypatch.setattr("backend.behavior.enforcer_gateway.gateway_call", fake_call)

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


def test_grant_credits_banks_and_claimable(monkeypatch):
    from backend.behavior import reward_days

    day = {"reward_day": False}
    state = {"qualified": 0, "used": 0, "granted": 0}

    def fake_call(op, payload=None, **kw):
        if op == "reward.grant_credits":
            state["granted"] += int((payload or {}).get("count") or 0)
            return {"ok": True, "reward_granted": state["granted"]}
        if op == "reward.status":
            available = max(0, state["qualified"] // 4 + state["granted"] - state["used"])
            return {
                "ok": True,
                "qualified_days": state["qualified"],
                "reward_earned": state["qualified"] // 4,
                "reward_granted": state["granted"],
                "reward_spent": state["used"],
                "reward_available": available,
                "days_to_next_reward": 4,
            }
        if op == "reward.claim":
            if state["granted"] - state["used"] <= 0:
                return {"ok": False, "error": "no_reward_available"}
            state["used"] += 1
            return {"ok": True}
        return {"ok": True}

    monkeypatch.setattr("backend.behavior.enforcer_gateway.gateway_call", fake_call)
    monkeypatch.setattr(reward_days.bible_store, "load_day", lambda _uid: dict(day))

    def save_day(_uid, value):
        day.clear()
        day.update(value)

    monkeypatch.setattr(reward_days.bible_store, "save_day", save_day)

    granted = reward_days.grant_credits(7, 3)
    assert granted["available"] == 3
    assert granted["granted"] == 3

    claimed = reward_days.claim_reward_day(7, confirm="REWARD", already_unlocked=False)
    assert claimed["ok"] is True
    assert claimed["available"] == 2
    assert day["reward_day"] is True
