"""Tests for away-from-desk prompt logging."""

from __future__ import annotations

from backend.behavior.tracker_away_prompt import away_min_idle_s, log_away_response


def test_away_min_idle_is_ten_minutes():
    assert away_min_idle_s() == 600.0


def test_log_away_response(tmp_path, monkeypatch):
    log_path = tmp_path / "away_log.json"
    monkeypatch.setattr("backend.behavior.tracker_away_prompt._LOG_PATH", log_path)
    item = log_away_response(choice="working", idle_seconds=720.0, user_id=1)
    assert item["choice"] == "working"
    assert item["idle_seconds"] == 720.0
    assert log_path.is_file()
