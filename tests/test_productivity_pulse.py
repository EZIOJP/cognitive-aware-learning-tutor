"""Tests for RescueTime-style Productivity Pulse."""

from __future__ import annotations

from backend.behavior.productivity_pulse import (
    attach_pulse,
    compute_pulse_from_sessions,
    level_weight,
    pulse_label,
)


def test_level_weight_bands():
    assert level_weight(95) == 100
    assert level_weight(70) == 75
    assert level_weight(50) == 50
    assert level_weight(30) == 25
    assert level_weight(10) == 0


def test_pulse_label():
    assert pulse_label(85) == "Very productive"
    assert pulse_label(65) == "Productive"
    assert pulse_label(45) == "Neutral"


def test_compute_pulse_mixed_sessions():
    sessions = [
        {
            "kind": "app",
            "seconds": 3600,
            "productivity_score": 95,
        },
        {
            "kind": "browser",
            "seconds": 1800,
            "productivity_score": 35,
            "sites": [
                {"site": "youtube.com", "seconds": 1800, "productivity_score": 15},
            ],
        },
    ]
    result = compute_pulse_from_sessions(sessions)
    assert result["total_seconds"] == 5400
    assert result["productive_seconds"] == 3600
    assert result["distracting_seconds"] == 1800
    assert 0 <= result["pulse"] <= 100
    assert result["pulse_label"]


def test_attach_pulse_merges_payload():
    payload = {
        "sessions": [{"kind": "app", "seconds": 600, "productivity_score": 80}],
        "total_seconds": 600,
    }
    out = attach_pulse(payload)
    assert out["pulse"] == 100
    assert out["productive_seconds"] == 600
