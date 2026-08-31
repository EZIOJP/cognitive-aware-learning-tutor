"""Comms health classifier + Edge close policy."""

from __future__ import annotations

from backend.behavior.comms_health import (
    classify_extension,
    extension_is_alive,
    may_close_edge,
    may_open_new_edge_window,
    note_extension_from_request,
    note_extension_heartbeat,
    record_dead_strike,
    snapshot,
)


def test_alive_does_not_close_edge():
    out = classify_extension(
        age_s=10,
        api_up=True,
        circuit_breaker=False,
        redirects_paused=False,
        server_mode="study",
        cached_mode="study",
    )
    assert out["status"] == "alive"
    assert out["may_close_edge"] is False
    assert out["may_open_edge"] is False


def test_stale_is_not_dead():
    out = classify_extension(
        age_s=90,
        api_up=True,
        circuit_breaker=False,
        redirects_paused=False,
        server_mode=None,
        cached_mode=None,
    )
    assert out["status"] == "stale"
    assert out["may_close_edge"] is False
    assert "dead_while_asleep" in out["false_negatives"]


def test_api_down_is_not_dead():
    out = classify_extension(
        age_s=400,
        api_up=False,
        circuit_breaker=False,
        redirects_paused=False,
        server_mode=None,
        cached_mode=None,
    )
    assert out["status"] == "stale"
    assert out["may_close_edge"] is False
    assert "dead_while_api_down" in out["false_negatives"]


def test_dead_with_api_up_may_close():
    out = classify_extension(
        age_s=400,
        api_up=True,
        circuit_breaker=False,
        redirects_paused=False,
        server_mode="study",
        cached_mode="study",
        startup_grace=False,
    )
    assert out["status"] == "dead"
    assert out["may_close_edge"] is True


def test_startup_grace_blocks_close():
    out = classify_extension(
        age_s=400,
        api_up=True,
        circuit_breaker=False,
        redirects_paused=False,
        server_mode="study",
        cached_mode="study",
        startup_grace=True,
    )
    assert out["status"] == "stale"
    assert out["may_close_edge"] is False
    assert "dead_during_startup_grace" in out["false_negatives"]


def test_free_mode_never_closes_edge():
    out = classify_extension(
        age_s=400,
        api_up=True,
        circuit_breaker=False,
        redirects_paused=False,
        server_mode="free",
        cached_mode="free",
        browser_mode="free",
        startup_grace=False,
    )
    assert out["may_close_edge"] is False
    assert "free_mode_hold" in out["cases"]


def test_partial_one_extension_alive():
    out = classify_extension(
        age_s=400,
        api_up=True,
        circuit_breaker=False,
        redirects_paused=False,
        server_mode="study",
        cached_mode="study",
        selftracker_age_s=8,
        calt_gate_age_s=400,
        startup_grace=False,
    )
    assert out["status"] == "alive"
    assert out["may_close_edge"] is False
    assert "one_extension_dead" in out["false_positives"]


def test_circuit_breaker_is_false_positive_alive():
    out = classify_extension(
        age_s=5,
        api_up=True,
        circuit_breaker=True,
        redirects_paused=True,
        server_mode="study",
        cached_mode="study",
    )
    assert out["status"] == "alive"
    assert "alive_but_not_enforcing" in out["false_positives"]
    assert out["may_close_edge"] is False


def test_expired_circuit_not_flagged():
    out = classify_extension(
        age_s=5,
        api_up=True,
        circuit_breaker=True,
        redirects_paused=True,
        server_mode="study",
        cached_mode="study",
        circuit_expired=True,
    )
    assert "alive_but_not_enforcing" not in out["false_positives"]
    assert "circuit_expired" in out["cases"]


def test_mode_mismatch_flagged():
    out = classify_extension(
        age_s=5,
        api_up=True,
        circuit_breaker=False,
        redirects_paused=False,
        server_mode="study",
        cached_mode="free",
    )
    assert "mode_mismatch" in out["false_positives"]


def test_spa_poll_without_header_does_not_mark_alive(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.behavior.comms_health._STATE_PATH", tmp_path / "comms.json")

    class H:
        def get(self, _k, default=""):
            return default

    class Req:
        headers = H()

    note_extension_from_request(Req(), server_mode="study")
    assert extension_is_alive() is False


def test_header_marks_alive(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.behavior.comms_health._STATE_PATH", tmp_path / "comms.json")

    class H(dict):
        def get(self, k, default=""):
            return dict.get(self, k, default)

    class Req:
        headers = H({"x-calt-extension": "selftracker", "x-calt-ext-mode": "study"})

    note_extension_from_request(Req(), server_mode="study")
    assert extension_is_alive() is True
    assert may_open_new_edge_window() is False
    assert may_close_edge(api_up=True) is False


def test_heartbeat_note(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.behavior.comms_health._STATE_PATH", tmp_path / "comms.json")
    note_extension_heartbeat(source="calt-gate", circuit_breaker=True)
    assert extension_is_alive() is True


def test_two_strike_resets_on_alive(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.behavior.comms_health._STATE_PATH", tmp_path / "comms.json")
    assert record_dead_strike(is_dead_candidate=True) == 1
    assert record_dead_strike(is_dead_candidate=True) == 2
    assert record_dead_strike(is_dead_candidate=False) == 0


def test_snapshot_two_strike_pending(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.behavior.comms_health._STATE_PATH", tmp_path / "comms.json")
    snap = snapshot(api_up=True, web_up=True)
    assert snap["edge_policy"]["may_close_edge"] is False
    assert snap["extension"]["status"] in ("unknown", "stale", "dead", "alive")


def test_observe_edge_presence_falling_edge(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.behavior.comms_health._STATE_PATH", tmp_path / "comms.json")
    from backend.behavior.comms_health import observe_edge_presence

    assert observe_edge_presence(False) is False  # never seen running
    assert observe_edge_presence(True) is False  # first seen alive
    assert observe_edge_presence(False) is True  # gone


def test_observe_edge_presence_skips_recent_tracker_close(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.behavior.comms_health._STATE_PATH", tmp_path / "comms.json")
    from backend.behavior.comms_health import mark_edge_closed, observe_edge_presence

    assert observe_edge_presence(True) is False
    mark_edge_closed()
    assert observe_edge_presence(False) is False


def test_observe_first_gone_with_recent_heartbeat(tmp_path, monkeypatch):
    """Tracker restart after a crash: Edge already gone, last ping still fresh."""
    monkeypatch.setattr("backend.behavior.comms_health._STATE_PATH", tmp_path / "comms.json")
    from backend.behavior.comms_health import note_extension_heartbeat, observe_edge_presence

    note_extension_heartbeat(source="selftracker")
    note_extension_heartbeat(source="calt-gate")
    assert observe_edge_presence(False) is True
