"""Canned dialogue text surfaces without double TTS."""

from __future__ import annotations

import time

from backend.behavior import gate_alerts
from backend.behavior.voice_agent import announce


def test_surface_dialogue_buffer(tmp_path, monkeypatch):
    monkeypatch.setattr(announce, "_FEED_PATH", tmp_path / "dialogue_feed.json")
    announce.reset_for_tests()
    monkeypatch.setattr(announce, "_FEED_PATH", tmp_path / "dialogue_feed.json")

    shown: list[str] = []
    announce.register_ui_callback(lambda t: shown.append(t))
    assert announce.surface_dialogue("Hello there")
    assert shown == ["Hello there"]
    assert announce.last_jarvis_line() == "Hello there"
    assert announce.recent_lines() == ["Hello there"]
    # Dedup within 2s
    assert announce.surface_dialogue("Hello there") is None
    assert shown == ["Hello there"]


def test_speak_alert_surfaces_once(monkeypatch, tmp_path):
    monkeypatch.setattr(announce, "_FEED_PATH", tmp_path / "dialogue_feed.json")
    announce.reset_for_tests()
    monkeypatch.setattr(announce, "_FEED_PATH", tmp_path / "dialogue_feed.json")

    spoken: list[str] = []
    shown: list[str] = []
    monkeypatch.setattr(
        "backend.behavior.voice_agent.io_speech.speak",
        lambda t: spoken.append(t),
    )
    monkeypatch.setattr(
        "backend.behavior.voice_agent.voice_agent_enabled",
        lambda: True,
    )
    gate_alerts.reset_speak_state_for_tests()
    # In-flight worker (e.g. bible_done_praise from a prior test) must finish first.
    deadline = time.time() + 3.0
    while time.time() < deadline and (gate_alerts.is_speaking() or gate_alerts._speak_q.qsize()):
        time.sleep(0.02)
    spoken.clear()
    shown.clear()
    announce.register_ui_callback(lambda t: shown.append(t))

    assert gate_alerts.speak_alert("Bible done — well played.", force=True)
    deadline = time.time() + 3.0
    while time.time() < deadline and len(spoken) < 1:
        time.sleep(0.02)
    assert shown == ["Bible done — well played."]
    assert spoken == ["Bible done — well played."]
