"""API duration labels + watch clock stamps (minutes stay numeric)."""

from __future__ import annotations

import json
from datetime import date, datetime
from types import SimpleNamespace

from backend.behavior.time_fmt import format_hours_mins_from_hours, optional_hours_label, optional_minutes_label
from backend.wearables.day_stamp import clock_fields_from_payload
from backend.wearables.ingest_service import serialize_wearable_daily


def test_format_hours_mins_from_hours():
    assert format_hours_mins_from_hours(0) == "0 hours 0 mins"
    assert format_hours_mins_from_hours(0.5) == "0 hours 30 mins"
    assert format_hours_mins_from_hours(7) == "7 hours"
    assert format_hours_mins_from_hours(7.5) == "7 hours 30 mins"
    assert format_hours_mins_from_hours(None) == "—"


def test_optional_labels_skip_none():
    assert optional_minutes_label(None) is None
    assert optional_minutes_label(50) == "0 hours 50 mins"
    assert optional_hours_label(None) is None
    assert optional_hours_label(4) == "4 hours"


def test_clock_fields_prefer_watch_meta():
    fields = clock_fields_from_payload(
        {
            "local_date": "2026-08-18",
            "tz_offset_min": 330,
            "captured_at": "2026-08-18T07:00:00+05:30",
            "meta": {"watch_local_date": "2026-08-17", "tz_offset_min": 345},
        }
    )
    assert fields["tz_offset_min"] == 345
    assert fields["watch_local_date"] == "2026-08-17"
    assert fields["captured_at"] == "2026-08-18T07:00:00+05:30"


def test_serialize_wearable_daily_exposes_labels_and_clock():
    payload = {
        "tz_offset_min": 330,
        "local_date": "2026-08-18",
        "captured_at": "2026-08-18T07:00:00+05:30",
        "meta": {"watch_local_date": "2026-08-18", "tz_offset_min": 330},
        "activity": {"sitting_min": 50},
    }
    row = SimpleNamespace(
        local_date=date(2026, 8, 18),
        source="mini_program",
        synced_at=None,
        sleep_hours=7.5,
        sleep_score=82,
        sleep_deep_min=90,
        steps=1000,
        step_target=8000,
        calories=None,
        calorie_target=None,
        distance_m=None,
        hr_last=None,
        hr_resting=None,
        spo2=None,
        stress=None,
        pai_today=None,
        pai_total=None,
        stand_hours=4,
        stand_target=12,
        battery_pct=None,
        last_captured_at=datetime(2026, 8, 18, 1, 30),
        last_dump_id="d1",
        last_chunk_id="c1",
        last_checksum="abc",
        payload_json=json.dumps(payload),
    )
    ser = serialize_wearable_daily(row)
    assert ser is not None
    assert ser["sitting_min"] == 50
    assert ser["sitting_label"] == "0 hours 50 mins"
    assert ser["sleep_label"] == "7 hours 30 mins"
    assert ser["sleep_deep_label"] == "1 hour 30 mins"
    assert ser["stand_label"] == "4 hours"
    assert ser["tz_offset_min"] == 330
    assert ser["watch_local_date"] == "2026-08-18"
    assert ser["captured_at"] == "2026-08-18T07:00:00+05:30"
