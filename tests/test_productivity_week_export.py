"""Smoke tests for productivity week export (timetable drafting)."""

from backend.planner.week_export import export_as_csv


def test_export_as_csv_headers():
    payload = {
        "by_day": [
            {
                "date": "2026-07-11",
                "weekday": "sat",
                "planned_minutes": 60,
                "actual_minutes": 45,
                "productive_minutes": 30,
                "effective_focus_minutes": 20,
                "adherence_pct": 75.0,
                "by_category_minutes": {"study": 30},
                "top_apps": [{"app": "code.exe", "minutes": 30}],
                "by_hour_minutes": {str(h): (10 if h == 10 else 0) for h in range(24)},
            }
        ],
        "suggested_timetable_hints": ["Protect 10:00 blocks."],
    }
    csv_text = export_as_csv(payload)
    assert "date,weekday,planned_minutes" in csv_text
    assert "2026-07-11,sat,60" in csv_text
    assert "Protect 10:00 blocks." in csv_text
