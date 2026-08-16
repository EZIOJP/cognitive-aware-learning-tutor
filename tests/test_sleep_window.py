"""Sleep window parsing from Zepp start_min/end_min — insight-based, not fixed times."""

from datetime import date

from backend.wearables.sleep_window import hours_on_calendar_day, resolve_sleep_for_day, sleep_datetimes


def test_overnight_minutes_past_1440():
    # Real: start 1450, end 1667 on wake day 2026-07-19 → Jul 19 00:10 – 03:47
    window = sleep_datetimes(
        local_date=date(2026, 7, 19),
        sleep={"start_min": 1450, "end_min": 1667, "total_min": 217},
    )
    assert window is not None
    start, end = window
    assert start.date() == date(2026, 7, 19)
    assert start.hour == 0 and start.minute == 10
    assert end.hour == 3 and end.minute == 47
    clipped = hours_on_calendar_day(date(2026, 7, 19), start, end)
    assert clipped is not None
    assert abs(clipped[1] - clipped[0] - 217 / 60) < 0.05


def test_overnight_evening_and_morning_clip():
    # start 1400 / end 1790 on wake day → prev 23:20 → wake 05:50
    window = sleep_datetimes(
        local_date=date(2026, 7, 26),
        sleep={"start_min": 1400, "end_min": 1790, "total_min": 390},
    )
    assert window is not None
    start, end = window
    assert start.date() == date(2026, 7, 25)
    assert start.hour == 23 and start.minute == 20
    assert end.date() == date(2026, 7, 26)
    assert end.hour == 5 and end.minute == 50
    eve = hours_on_calendar_day(date(2026, 7, 25), start, end)
    morn = hours_on_calendar_day(date(2026, 7, 26), start, end)
    assert eve is not None and abs(eve[0] - 23.333) < 0.02 and abs(eve[1] - 24.0) < 0.02
    assert morn is not None and abs(morn[0] - 0.0) < 0.02 and abs(morn[1] - 5.833) < 0.02
    assert hours_on_calendar_day(date(2026, 7, 24), start, end) is None


def test_same_day_nap():
    window = sleep_datetimes(
        local_date=date(2026, 7, 26),
        sleep={"start_min": 780, "end_min": 840, "total_min": 60},
    )
    assert window is not None
    start, end = window
    assert start.date() == end.date() == date(2026, 7, 26)
    assert start.hour == 13 and end.hour == 14


def test_morning_only_after_midnight():
    window = sleep_datetimes(
        local_date=date(2026, 7, 26),
        sleep={"start_min": 100, "end_min": 400, "total_min": 300},
    )
    assert window is not None
    start, end = window
    assert start.date() == end.date() == date(2026, 7, 26)
    assert start.hour == 1 and start.minute == 40
    assert end.hour == 6 and end.minute == 40


def test_duration_only_no_fake_wedge():
    window = sleep_datetimes(
        local_date=date(2026, 7, 19),
        sleep={"total_min": 420, "start_min": None, "end_min": -1},
    )
    assert window is None
    view = resolve_sleep_for_day(
        day=date(2026, 7, 19),
        sleep_hours=7.0,
        sleep_payload={"total_min": 420, "start_min": None, "end_min": -1},
        wearable_local_date=date(2026, 7, 19),
    )
    assert view["sleep_minutes"] == 420
    assert view["has_timed_window"] is False


def test_resolve_clips_only_intersecting_day():
    sleep = {"start_min": 1400, "end_min": 1790, "total_min": 390}
    wake = date(2026, 7, 26)
    eve = resolve_sleep_for_day(
        day=date(2026, 7, 25), sleep_hours=6.5, sleep_payload=sleep, wearable_local_date=wake
    )
    morn = resolve_sleep_for_day(
        day=wake, sleep_hours=6.5, sleep_payload=sleep, wearable_local_date=wake
    )
    other = resolve_sleep_for_day(
        day=date(2026, 7, 24), sleep_hours=6.5, sleep_payload=sleep, wearable_local_date=wake
    )
    assert eve["has_timed_window"] and abs(eve["startHour"] - 23.333) < 0.02
    assert morn["has_timed_window"] and abs(morn["endHour"] - 5.833) < 0.02
    assert other["has_timed_window"] is False and other["sleep_minutes"] == 0


def test_wake_day_ring_is_morning_clip_only():
    """Overnight on wake day: morning wedge only (evening belongs on bed day)."""
    sleep = {"start_min": 1380, "end_min": 1800, "total_min": 420}
    wake = date(2026, 7, 25)
    bed = date(2026, 7, 24)
    morn = resolve_sleep_for_day(
        day=wake, sleep_hours=7.0, sleep_payload=sleep, wearable_local_date=wake
    )
    eve = resolve_sleep_for_day(
        day=bed, sleep_hours=7.0, sleep_payload=sleep, wearable_local_date=wake
    )
    assert morn["has_timed_window"]
    ring = morn["ring_clips"]
    assert len(ring) == 1
    assert ring[0].get("crossesMidnight") is False
    assert abs(ring[0]["startHour"] - 0.0) < 0.02
    assert abs(ring[0]["endHour"] - 6.0) < 0.02
    assert abs(morn["sleep_minutes"] - 360) < 2
    assert eve["has_timed_window"]
    assert abs(eve["ring_clips"][0]["startHour"] - 23.0) < 0.02
    assert abs(eve["ring_clips"][0]["endHour"] - 24.0) < 0.02


def test_large_nap_offsets_anchor_to_wake_day():
    """Aug-5-style naps with start≥1440 must land on wake day, not day+1."""
    from backend.wearables.sleep_window import nap_datetimes, sleep_bouts

    wake = date(2026, 8, 5)
    sleep = {
        "start_min": 1131,
        "end_min": 1513,
        "total_min": 382,
        "naps": [
            {"start": 2508, "stop": 2824, "length": 305},
            {"start": 1783, "stop": 1852, "length": 54},
        ],
    }
    naps = nap_datetimes(local_date=wake, sleep=sleep)
    assert len(naps) == 2
    evening = next(n for n in naps if n[0].hour >= 12)
    morning = next(n for n in naps if n[0].hour < 12)
    assert evening[0].date() == wake
    assert evening[0].hour == 17 and evening[0].minute == 48
    assert evening[1].hour == 23 and evening[1].minute == 4
    assert morning[0].date() == wake
    assert morning[0].hour == 5 and morning[0].minute == 43
    bouts = sleep_bouts(local_date=wake, sleep=sleep)
    assert all(b[0].date() <= wake for b in bouts)
    assert not any(b[0].date() > wake for b in bouts)


def test_naps_paint_daytime():
    sleep = {
        "start_min": 1400,
        "end_min": 1790,
        "total_min": 390,
        "naps": [{"start": 780, "stop": 870, "length": 90}],
    }
    wake = date(2026, 7, 26)
    view = resolve_sleep_for_day(
        day=wake, sleep_hours=6.5, sleep_payload=sleep, wearable_local_date=wake
    )
    assert view["has_timed_window"]
    clips = view["clips"]
    assert any(abs(c["startHour"] - 0.0) < 0.02 and abs(c["endHour"] - 5.833) < 0.05 for c in clips)
    assert any(abs(c["startHour"] - 13.0) < 0.02 and abs(c["endHour"] - 14.5) < 0.02 for c in clips)


def test_no_borrow_yesterday_onto_empty_day():
    sleep = {"start_min": 1450, "end_min": 1667, "total_min": 217}
    view = resolve_sleep_for_day(
        day=date(2026, 7, 20),
        sleep_hours=3.62,
        sleep_payload=sleep,
        wearable_local_date=date(2026, 7, 19),
    )
    assert view["has_timed_window"] is False
    assert view["sleep_minutes"] == 0


def test_fill_end_from_total():
    window = sleep_datetimes(
        local_date=date(2026, 7, 26),
        sleep={"start_min": 1400, "end_min": None, "total_min": 390},
    )
    assert window is not None
    start, end = window
    assert start.hour == 23 and start.minute == 20
    assert end.hour == 5 and end.minute == 50


def test_no_sleep():
    assert sleep_datetimes(local_date=date(2026, 7, 19), sleep={"total_min": 0, "end_min": -1}) is None


def test_partition_around_sleep_marks_overlap_idle():
    from datetime import datetime, timezone

    from backend.wearables.sleep_window import partition_around_sleep

    tz = timezone.utc
    start = datetime(2026, 7, 25, 20, 0, tzinfo=tz)
    end = datetime(2026, 7, 26, 8, 0, tzinfo=tz)
    sleep = (
        datetime(2026, 7, 25, 22, 0, tzinfo=tz),
        datetime(2026, 7, 26, 6, 0, tzinfo=tz),
    )
    pieces = partition_around_sleep(start, end, [sleep])
    assert pieces == [
        (datetime(2026, 7, 25, 20, 0, tzinfo=tz), datetime(2026, 7, 25, 22, 0, tzinfo=tz), False),
        (datetime(2026, 7, 25, 22, 0, tzinfo=tz), datetime(2026, 7, 26, 6, 0, tzinfo=tz), True),
        (datetime(2026, 7, 26, 6, 0, tzinfo=tz), datetime(2026, 7, 26, 8, 0, tzinfo=tz), False),
    ]


def test_partition_fully_inside_sleep_is_idle():
    from datetime import datetime, timezone

    from backend.wearables.sleep_window import partition_around_sleep

    tz = timezone.utc
    start = datetime(2026, 7, 25, 23, 0, tzinfo=tz)
    end = datetime(2026, 7, 26, 1, 0, tzinfo=tz)
    sleep = (
        datetime(2026, 7, 25, 22, 0, tzinfo=tz),
        datetime(2026, 7, 26, 6, 0, tzinfo=tz),
    )
    pieces = partition_around_sleep(start, end, [sleep])
    assert pieces == [(start, end, True)]
