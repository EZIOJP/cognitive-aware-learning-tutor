"""Tests for CALT Gate extension redirect logging."""

from backend.behavior.gate_extension_log import append_gate_extension_event


def test_append_gate_extension_event_writes_jsonl(tmp_path, monkeypatch):
    log_path = tmp_path / "gate_extension.log"
    monkeypatch.setattr("backend.behavior.gate_extension_log._LOG_PATH", log_path)
    monkeypatch.setattr(
        "backend.behavior.gate_alerts.enqueue_alert",
        lambda *a, **k: {"kind": a[0]},
    )
    append_gate_extension_event(
        {
            "event": "soft_land",
            "detail": "https://www.youtube.com/watch?v=1",
            "notify": True,
        }
    )
    text = log_path.read_text(encoding="utf-8")
    assert "soft_land" in text
    assert "youtube.com" in text
