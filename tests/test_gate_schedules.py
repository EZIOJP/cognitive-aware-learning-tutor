"""Tests for gate schedules and study mode nudge."""

from __future__ import annotations

from datetime import datetime, timezone

from backend.behavior.gate_schedules import save_gate_schedules, scheduled_mode
from backend.behavior.study_mode_nudge import arm_study_mode_nudge, study_nudge_active


def test_scheduled_mode_when_enabled(tmp_path, monkeypatch):
    path = tmp_path / "gate_schedules.json"
    monkeypatch.setattr("backend.behavior.gate_schedules._SCHEDULE_PATH", path)
    save_gate_schedules({
        "enabled": True,
        "windows": [{
            "id": "w1",
            "label": "Work",
            "days": [0, 1, 2, 3, 4],
            "start": "09:00",
            "end": "18:00",
            "mode": "study",
        }],
    })
    dt = datetime(2026, 8, 18, 10, 0, tzinfo=timezone.utc)
    assert scheduled_mode(dt) == "study"


def test_study_nudge_active(tmp_path, monkeypatch):
    path = tmp_path / "nudge.json"
    monkeypatch.setattr("backend.behavior.study_mode_nudge._NUDGE_PATH", path)
    assert study_nudge_active() is False
    arm_study_mode_nudge(minutes=30, path=path)
    assert study_nudge_active() is True
