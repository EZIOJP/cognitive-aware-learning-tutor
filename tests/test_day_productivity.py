"""Tests for unified day-status productivity block + ActivityWatch export."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from backend.behavior.activitywatch_export import export_activitywatch_payload
from backend.behavior.day_productivity import build_productivity_snapshot


def test_build_productivity_snapshot_empty(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.behavior.day_productivity._tracker_user_ids", lambda _db, uid: [uid])
    db = MagicMock()
    with (
        patch("backend.behavior.day_productivity._sessions_for_day", return_value=([], 0)),
        patch(
            "backend.behavior.day_productivity.build_goals_status",
            return_value={
                "date": "2026-08-04",
                "goals": [{
                    "id": "productive_daily_goal",
                    "pct": 0,
                    "met": False,
                    "target_seconds": 14400,
                    "current_seconds": 0,
                }],
                "alerts": [],
                "productive_seconds": 0,
                "total_seconds": 0,
            },
        ),
        patch(
            "backend.behavior.day_productivity._focus_quality_compact",
            return_value={"score": 100, "label": "No on-plan data", "switches": 0},
        ),
        patch(
            "backend.behavior.day_productivity._weekly_snippet",
            return_value={"avg_pulse": 0, "goal_met_days": 0, "tracked_days": 0},
        ),
    ):
        out = build_productivity_snapshot(db, user_id=1)
    assert out["pulse"] == 0
    assert out["goal_pct"] == 0
    assert out["focus_quality"]["score"] == 100
    assert out["study_mode_nudge"]["active"] is False


def test_export_activitywatch_payload_shape():
    db = MagicMock()
    row = MagicMock()
    row.session_id = "sess-1"
    row.start_time = datetime(2026, 8, 4, 10, 0, tzinfo=timezone.utc)
    row.end_time = datetime(2026, 8, 4, 10, 5, tzinfo=timezone.utc)
    row.app_name = "chrome.exe"
    row.window_title = "docs.google.com — Doc"
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [row]

    from datetime import date

    payload = export_activitywatch_payload(db, [1], date(2026, 8, 4))
    assert payload["ok"] is True
    assert payload["format"] == "activitywatch/events/v1"
    assert payload["event_count"] == 1
    assert payload["events"][0]["duration"] == 300.0
    assert payload["events"][0]["data"]["app"] == "chrome.exe"
