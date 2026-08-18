"""Tests for focus quality scoring."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from backend.behavior.focus_quality import compute_focus_quality


def test_focus_quality_high_with_stable_app():
    now = datetime.now(UTC)
    rows = [
        {
            "start_time": now - timedelta(minutes=30),
            "end_time": now,
            "app_name": "code.exe",
            "productivity_score": 95,
        },
    ]
    planned = [(now - timedelta(hours=1), now + timedelta(minutes=1))]
    result = compute_focus_quality(rows, planned_intervals=planned)
    assert result["score"] >= 80
    assert result["switches"] == 0


def test_focus_quality_drops_with_switches():
    now = datetime.now(UTC)
    rows = [
        {
            "start_time": now - timedelta(minutes=20),
            "end_time": now - timedelta(minutes=10),
            "app_name": "code.exe",
            "productivity_score": 95,
        },
        {
            "start_time": now - timedelta(minutes=10),
            "end_time": now,
            "app_name": "youtube.com",
            "productivity_score": 15,
        },
    ]
    planned = [(now - timedelta(hours=1), now + timedelta(minutes=1))]
    result = compute_focus_quality(rows, planned_intervals=planned)
    assert result["switches"] >= 1
    assert result["score"] < 95
