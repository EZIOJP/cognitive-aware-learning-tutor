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


def test_focus_quality_accepts_iso_string_times():
    """Serialized sessions (iso_utc Z strings) and string planner intervals."""
    now = datetime.now(UTC)
    start = now - timedelta(minutes=30)
    end = now
    rows = [
        {
            "start_time": start.isoformat().replace("+00:00", "Z"),
            "end_time": end.isoformat().replace("+00:00", "Z"),
            "app_name": "code.exe",
            "productivity_score": 95,
        },
    ]
    planned = [
        (
            (now - timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
            (now + timedelta(minutes=1)).isoformat().replace("+00:00", "Z"),
        )
    ]
    result = compute_focus_quality(rows, planned_intervals=planned)
    assert result["score"] >= 80
    assert result["switches"] == 0
    assert result["on_plan_minutes"] > 0


def test_focus_quality_skips_invalid_interval_strings():
    now = datetime.now(UTC)
    rows = [
        {
            "start_time": (now - timedelta(minutes=20)).isoformat().replace("+00:00", "Z"),
            "end_time": now.isoformat().replace("+00:00", "Z"),
            "app_name": "code.exe",
            "productivity_score": 95,
        },
    ]
    planned = [
        ("not-a-datetime", "also-bad"),
        (
            (now - timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
            (now + timedelta(minutes=1)).isoformat().replace("+00:00", "Z"),
        ),
    ]
    result = compute_focus_quality(rows, planned_intervals=planned)
    assert result["on_plan_minutes"] > 0
    assert result["score"] >= 80


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
