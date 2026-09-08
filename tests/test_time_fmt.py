"""Hours + minutes display labels (storage stays in minutes)."""

from backend.behavior.time_fmt import format_duration_spoken, format_hours_mins, enrich_duration_fmt


def test_format_duration_spoken() -> None:
    assert format_duration_spoken(50) == "50 mins"
    assert format_duration_spoken(90) == "1 hour 30 mins"
    enriched = enrich_duration_fmt({"focus_min": 90})
    assert enriched["focus_hm"] == "1 hour 30 mins"


def test_format_hours_mins_examples():
    assert format_hours_mins(0) == "0 hours 0 mins"
    assert format_hours_mins(1) == "0 hours 1 min"
    assert format_hours_mins(50) == "0 hours 50 mins"
    assert format_hours_mins(60) == "1 hour"
    assert format_hours_mins(90) == "1 hour 30 mins"
    assert format_hours_mins(240) == "4 hours"
    assert format_hours_mins(241) == "4 hours 1 min"
    assert format_hours_mins(None) == "—"
    assert format_hours_mins("nope") == "—"
