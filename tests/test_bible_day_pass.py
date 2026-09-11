"""Weekly Bible day-pass quota — enforced by calt_enforcer gateway."""

from backend.bible import store


def test_request_day_pass_goes_through_gateway(monkeypatch):
    calls = []

    def fake_call(op, payload=None, **kw):
        calls.append((op, payload))
        return {"ok": True, "passes_limit": 2, "passes_used": 1, "pass_today": True}

    monkeypatch.setattr("backend.behavior.enforcer_gateway.gateway_call", fake_call)
    monkeypatch.setattr(store, "load_day", lambda _uid: {"day_pass": False, "game_consumed_seconds": 0})
    monkeypatch.setattr(store, "save_day", lambda _uid, _day: None)
    monkeypatch.setattr(store, "summary", lambda _uid: {"day_pass": True})

    out = store.request_day_pass(1, confirm="PASS")
    assert out["ok"] is True
    assert calls[0] == ("day.grant_pass", {"confirm": "PASS"})
    assert any(op == "day.status" for op, _ in calls)


def test_day_pass_requires_confirm(monkeypatch):
    def fake_call(op, payload=None, **kw):
        return {"ok": False, "error": "confirm_required"}

    monkeypatch.setattr("backend.behavior.enforcer_gateway.gateway_call", fake_call)
    try:
        store.request_day_pass(1, confirm="nope")
        assert False, "expected ValueError"
    except ValueError as e:
        assert "PASS" in str(e)


def test_day_pass_quota(monkeypatch):
    def fake_call(op, payload=None, **kw):
        return {"ok": False, "error": "pass_quota_exhausted"}

    monkeypatch.setattr("backend.behavior.enforcer_gateway.gateway_call", fake_call)
    try:
        store.request_day_pass(1, confirm="PASS")
        assert False, "expected quota error"
    except ValueError as e:
        assert "No day passes" in str(e)
