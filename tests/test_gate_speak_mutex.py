"""Speak mutex / single-stream TTS — no overlapping audio."""

from __future__ import annotations

import threading
import time

from backend.behavior import gate_alerts


def test_speak_alert_serializes_force_calls(monkeypatch):
    gate_alerts.reset_speak_state_for_tests()
    spoken: list[str] = []
    lock = threading.Lock()
    concurrent = {"n": 0, "max": 0}

    def fake_speak(text: str) -> None:
        with lock:
            concurrent["n"] += 1
            concurrent["max"] = max(concurrent["max"], concurrent["n"])
        time.sleep(0.05)
        spoken.append(text)
        with lock:
            concurrent["n"] -= 1

    monkeypatch.setattr(
        "backend.behavior.voice_agent.io_speech.speak",
        fake_speak,
    )
    monkeypatch.setattr(
        "backend.behavior.voice_agent.voice_agent_enabled",
        lambda: True,
    )

    assert gate_alerts.speak_alert("first line", force=True)
    assert gate_alerts.speak_alert("second line", force=True)

    deadline = time.time() + 5.0
    while time.time() < deadline and len(spoken) < 2:
        time.sleep(0.02)

    assert spoken == ["first line", "second line"]
    assert concurrent["max"] == 1


def test_speak_alert_sync_waits(monkeypatch):
    gate_alerts.reset_speak_state_for_tests()
    order: list[str] = []

    def fake_speak(text: str) -> None:
        order.append(f"start:{text}")
        time.sleep(0.03)
        order.append(f"end:{text}")

    monkeypatch.setattr(
        "backend.behavior.voice_agent.io_speech.speak",
        fake_speak,
    )
    monkeypatch.setattr(
        "backend.behavior.voice_agent.voice_agent_enabled",
        lambda: True,
    )

    assert gate_alerts.speak_alert_sync("a", force=True)
    assert "end:a" in order
    assert gate_alerts.speak_alert_sync("b", force=True)
    assert order.index("end:a") < order.index("start:b")


def test_notify_block_does_not_speak(monkeypatch):
    gate_alerts.reset_speak_state_for_tests()
    spoken: list[str] = []
    monkeypatch.setattr(
        "backend.behavior.voice_agent.io_speech.speak",
        lambda t: spoken.append(t),
    )
    monkeypatch.setattr(
        "backend.behavior.voice_agent.voice_agent_enabled",
        lambda: True,
    )
    item = gate_alerts.notify_block("watch", detail="youtube")
    assert item.get("message")
    time.sleep(0.1)
    assert spoken == []
    pending = gate_alerts.drain_alerts()
    assert len(pending) >= 1
