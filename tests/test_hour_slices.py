"""Unit tests for planner hour_slices lane assignment."""

from datetime import datetime, timedelta, timezone

from backend.planner.hour_slices import compute_hour_slices, merge_for_hour_slices


TZ = "Asia/Kolkata"


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _sess(
    sid: str,
    start: datetime,
    end: datetime,
    *,
    app: str = "Code.exe",
    category: str = "study",
    source: str = "desktop_tracker",
) -> dict:
    return {
        "session_id": sid,
        "start_time": _iso(start),
        "end_time": _iso(end),
        "app_name": app,
        "category": category,
        "source": source,
        "window_title": app,
    }


def test_sleep_reserves_lane_zero_desktop_starts_at_one():
    # Local 2026-07-26 05:00–06:00 IST = UTC 2026-07-25 23:30–00:30
    base = datetime(2026, 7, 26, 5, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    sessions = [
        _sess(
            "sleep:1",
            base,
            base + timedelta(hours=1),
            app="Amazfit",
            category="Sleep",
            source="wearable_sleep",
        ),
        _sess("desk-1", base + timedelta(minutes=10), base + timedelta(minutes=50), app="Chrome"),
    ]
    slices = compute_hour_slices(sessions, tz_name=TZ)
    assert len(slices) == 1
    by_src = {s["source"]: s for s in slices[0]["segments"]}
    assert by_src["sleep"]["lane_index"] == 0
    assert by_src["desktop"]["lane_index"] == 1
    assert slices[0]["lane_count"] == 2


def test_cross_hour_pin_stability_same_group():
    base = datetime(2026, 7, 26, 5, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    # One contiguous Chrome run across 05–07
    sessions = [
        _sess("c1", base, base + timedelta(hours=2, minutes=30), app="Chrome"),
        # Overlap only in hour 6 with a second app so lane_count grows
        _sess(
            "v1",
            base + timedelta(hours=1, minutes=5),
            base + timedelta(hours=1, minutes=55),
            app="VLC",
        ),
    ]
    slices = compute_hour_slices(sessions, tz_name=TZ)
    assert len(slices) >= 2
    chrome_lanes = []
    chrome_gid = None
    for sl in slices:
        for seg in sl["segments"]:
            if seg["app_or_label"].lower().startswith("chrome"):
                chrome_lanes.append(seg["lane_index"])
                chrome_gid = seg["session_group_id"]
    assert chrome_gid
    assert len(set(chrome_lanes)) == 1, f"Chrome lane should be stable, got {chrome_lanes}"


def test_desktop_pin_skips_reserved_sleep_lane():
    """Desktop alone in hour N on lane 0; next hour has sleep → desktop must leave 0."""
    base = datetime(2026, 7, 26, 4, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    sessions = [
        _sess("c1", base, base + timedelta(hours=2), app="Chrome"),
        _sess(
            "sleep:1",
            base + timedelta(hours=1),
            base + timedelta(hours=2),
            app="Amazfit",
            category="Sleep",
            source="wearable_sleep",
        ),
    ]
    slices = compute_hour_slices(sessions, tz_name=TZ)
    by_hour = {s["hour"]: s for s in slices}
    h4 = by_hour[4]
    h5 = by_hour[5]
    chrome4 = next(s for s in h4["segments"] if s["source"] == "desktop")
    chrome5 = next(s for s in h5["segments"] if s["source"] == "desktop")
    sleep5 = next(s for s in h5["segments"] if s["source"] == "sleep")
    assert chrome4["lane_index"] == 0
    assert sleep5["lane_index"] == 0
    assert chrome5["lane_index"] >= 1


def test_partial_minute_geometry_not_full_hour():
    base = datetime(2026, 7, 26, 8, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    sessions = [
        _sess("c1", base + timedelta(minutes=15), base + timedelta(minutes=40), app="Notion"),
    ]
    slices = compute_hour_slices(sessions, tz_name=TZ)
    seg = slices[0]["segments"][0]
    assert seg["start_min"] == 15
    assert seg["end_min"] == 40
    assert seg["duration_min"] == 25


def test_session_group_id_is_merge_key_not_raw_id():
    base = datetime(2026, 7, 26, 9, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    # Two flushes of same app within merge gap → one group
    sessions = [
        _sess("raw-a", base, base + timedelta(minutes=20), app="ACShadows"),
        _sess(
            "raw-b",
            base + timedelta(minutes=21),
            base + timedelta(minutes=50),
            app="ACShadows",
        ),
    ]
    runs = merge_for_hour_slices(sessions)
    assert len(runs) == 1
    assert runs[0].session_group_id.startswith("app:acshadows|")
    assert set(runs[0].session_ids) == {"raw-a", "raw-b"}


def test_interleaved_same_app_stays_split_when_other_app_between():
    """Cursor → Edge → Cursor: keep two Cursor blocks (don't glue across Edge)."""
    base = datetime(2026, 7, 26, 4, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    sessions = [
        _sess("c1", base, base + timedelta(minutes=10), app="Cursor"),
        _sess("e1", base + timedelta(minutes=10), base + timedelta(minutes=15), app="msedge"),
        _sess("c2", base + timedelta(minutes=15), base + timedelta(minutes=40), app="Cursor"),
    ]
    runs = merge_for_hour_slices(sessions)
    cursors = [r for r in runs if r.app_or_label.lower() == "cursor"]
    edges = [r for r in runs if r.app_or_label.lower() == "msedge"]
    assert len(cursors) == 2
    assert len(edges) == 1
    assert cursors[0].session_ids == ["c1"]
    assert cursors[1].session_ids == ["c2"]


def test_contiguous_same_app_merges_without_intervening():
    """Cursor → Cursor with small gap and nothing between → one whole block."""
    base = datetime(2026, 7, 26, 4, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    sessions = [
        _sess("c1", base, base + timedelta(minutes=10), app="Cursor", category="IDE / Code Editor"),
        _sess(
            "c2",
            base + timedelta(minutes=11),
            base + timedelta(minutes=40),
            app="Cursor",
            category="IDE / Code Editor",
        ),
    ]
    runs = merge_for_hour_slices(sessions)
    cursors = [r for r in runs if r.app_or_label.lower() == "cursor"]
    assert len(cursors) == 1
    assert set(cursors[0].session_ids) == {"c1", "c2"}


def test_title_corrects_misattributed_cursor_to_zen():
    """app=Cursor + title “… — Zen Browser” must merge/label as zen, not Cursor."""
    base = datetime(2026, 7, 26, 4, 37, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    sessions = [
        {
            "session_id": "bad",
            "start_time": _iso(base),
            "end_time": _iso(base + timedelta(minutes=9)),
            "app_name": "Cursor",
            "category": "IDE / Code Editor",
            "source": "desktop_tracker",
            "window_title": "Rive | Watch | The Rookie | S8-E1 — Zen Browser",
        }
    ]
    runs = merge_for_hour_slices(sessions)
    assert len(runs) == 1
    assert runs[0].app_or_label.lower() == "zen"
    assert runs[0].session_group_id.startswith("app:zen|")
    assert runs[0].category == "Video Streaming"


def test_large_gap_keeps_separated_same_app():
    """Same app with gap > merge window stays two blocks — do not force-glue."""
    base = datetime(2026, 7, 26, 4, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    sessions = [
        _sess("c1", base, base + timedelta(minutes=10), app="Cursor"),
        _sess(
            "c2",
            base + timedelta(minutes=30),  # 20 min idle = 1200s > 900s gap
            base + timedelta(minutes=40),
            app="Cursor",
        ),
    ]
    runs = merge_for_hour_slices(sessions)
    cursors = [r for r in runs if r.app_or_label.lower() == "cursor"]
    assert len(cursors) == 2
