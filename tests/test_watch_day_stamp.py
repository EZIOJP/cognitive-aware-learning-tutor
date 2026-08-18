"""Watch local_date + tz_offset must win over phone/PC 'today'."""

from datetime import date, datetime, timedelta, timezone

from backend.wearables.day_stamp import resolve_ingest_day, tz_from_offset_min
from backend.wearables.sleep_window import sleep_datetimes


def test_watch_local_date_wins_over_host_today():
    host = date(2026, 8, 18)
    day = resolve_ingest_day(
        {
            "local_date": "2026-08-17",
            "source": "mini_program",
            "meta": {"watch_local_date": "2026-08-17", "tz_offset_min": 330},
        },
        host_today=host,
    )
    assert day == date(2026, 8, 17)


def test_invalid_watch_date_falls_back_to_host():
    host = date(2026, 8, 18)
    day = resolve_ingest_day({"local_date": "nope", "source": "mini_program"}, host_today=host)
    assert day == host


def test_missing_date_uses_host():
    host = date(2026, 8, 18)
    assert resolve_ingest_day({}, host_today=host) == host


def test_far_skew_without_queue_keeps_host():
    host = date(2026, 8, 18)
    day = resolve_ingest_day(
        {"local_date": "2026-01-01", "source": "mini_program"},
        host_today=host,
    )
    assert day == host


def test_queued_chunk_allows_week_old_watch_day():
    host = date(2026, 8, 18)
    day = resolve_ingest_day(
        {
            "local_date": "2026-08-12",
            "source": "mini_program",
            "meta": {"queued_sleep_snapshot": True, "chunk": {"part": 1, "total": 4}},
        },
        host_today=host,
    )
    assert day == date(2026, 8, 12)


def test_tz_offset_min_is_fixed_offset():
    tz = tz_from_offset_min(330)
    assert tz.utcoffset(datetime(2026, 8, 18)) == timedelta(minutes=330)


def test_sleep_window_uses_watch_tz_offset():
    local_date = date(2026, 8, 18)
    sleep = {"start_min": 1380, "end_min": 1800, "total_min": 420}
    start, end = sleep_datetimes(
        local_date=local_date,
        sleep=sleep,
        tz=tz_from_offset_min(330),
    )
    assert start.utcoffset() == timedelta(minutes=330)
    assert end.date() == local_date
    assert start.hour == 23
