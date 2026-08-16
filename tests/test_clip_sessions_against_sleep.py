"""Clip desktop sessions that fall inside sleep; sleep wins on the calendar."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from backend.wearables.sleep_window import clip_session_dicts_against_sleep


def test_clip_drops_cursor_fully_inside_sleep():
    sleep = [
        (
            datetime(2026, 8, 5, 17, 48, tzinfo=UTC),
            datetime(2026, 8, 5, 23, 4, tzinfo=UTC),
        )
    ]
    sessions = [
        {
            "session_id": "cursor-idle",
            "source": "desktop_tracker",
            "category": "IDE / Code Editor",
            "app_name": "Cursor.exe",
            "start_time": "2026-08-05T18:00:00+00:00",
            "end_time": "2026-08-05T22:00:00+00:00",
        },
        {
            "session_id": "sleep:1",
            "source": "wearable_sleep",
            "category": "Sleep",
            "app_name": "Amazfit",
            "start_time": "2026-08-05T17:48:00+00:00",
            "end_time": "2026-08-05T23:04:00+00:00",
        },
    ]
    out = clip_session_dicts_against_sleep(sessions, sleep)
    assert len(out) == 1
    assert out[0]["source"] == "wearable_sleep"


def test_clip_keeps_awake_shoulders():
    sleep = [
        (
            datetime(2026, 8, 5, 1, 0, tzinfo=UTC),
            datetime(2026, 8, 5, 5, 0, tzinfo=UTC),
        )
    ]
    sessions = [
        {
            "session_id": "long",
            "source": "desktop_tracker",
            "category": "IDE / Code Editor",
            "app_name": "Cursor.exe",
            "start_time": datetime(2026, 8, 5, 0, 0, tzinfo=UTC).isoformat(),
            "end_time": datetime(2026, 8, 5, 6, 0, tzinfo=UTC).isoformat(),
        }
    ]
    out = clip_session_dicts_against_sleep(sessions, sleep)
    assert len(out) == 2
    starts = sorted(datetime.fromisoformat(s["start_time"]) for s in out)
    ends = sorted(datetime.fromisoformat(s["end_time"]) for s in out)
    assert starts[0].hour == 0
    assert ends[0].hour == 1
    assert starts[1].hour == 5
    assert ends[1].hour == 6
