"""Morning order scheduling rules."""

from __future__ import annotations

from datetime import date

import pytest


def test_study_floor_after_breakfast_routines() -> None:
    from backend.planner.morning_order import morning_study_floor_min

    routines = [
        {"title": "Bible", "category": "spiritual", "start_time": "06:00", "end_time": "06:30", "enabled": True, "days": ["mon"]},
        {"title": "Bath", "category": "personal", "start_time": "06:30", "end_time": "07:00", "enabled": True, "days": ["mon"]},
        {"title": "Breakfast", "category": "food", "start_time": "07:00", "end_time": "07:30", "enabled": True, "days": ["mon"]},
    ]
    day = date(2026, 9, 7)  # Monday
    floor = morning_study_floor_min(day=day, routines=routines)
    assert floor >= 7 * 60 + 40  # after 07:30 + buffer


def test_study_pushed_after_morning_floor() -> None:
    from backend.planner.morning_order import enforce_morning_order

    day = date(2026, 9, 7)
    blocks = [
        {
            "title": "AI/ML study",
            "category": "AI/ML",
            "start_at": "2026-09-07T08:00:00+05:30",
            "end_at": "2026-09-07T08:30:00+05:30",
            "source": "study",
        },
        {
            "title": "Breakfast",
            "category": "food",
            "start_at": "2026-09-07T07:00:00+05:30",
            "end_at": "2026-09-07T07:30:00+05:30",
            "source": "existing",
        },
    ]
    out = enforce_morning_order(blocks, day=day)
    study = next(b for b in out if "study" in str(b.get("title")).lower())
    assert "08:00" not in str(study.get("start_at"))


def test_break_after_each_study_task() -> None:
    from backend.planner.morning_order import insert_breaks_after_study_tasks

    day = date(2026, 9, 7)
    blocks = [
        {
            "title": "Scaler",
            "category": "study",
            "start_at": "2026-09-07T09:00:00+05:30",
            "end_at": "2026-09-07T10:00:00+05:30",
            "source": "study",
        },
    ]
    out = insert_breaks_after_study_tasks(blocks, day=day)
    assert len(out) == 2
    assert str(out[1].get("source")) == "break"


def test_day_starts_with_routine_not_study() -> None:
    from backend.planner.morning_order import apply_day_rhythm

    day = date(2026, 9, 7)
    blocks = [
        {
            "title": "Study first",
            "category": "study",
            "start_at": "2026-09-07T06:30:00+05:30",
            "end_at": "2026-09-07T07:30:00+05:30",
            "source": "study",
        },
        {
            "title": "Bible",
            "category": "spiritual",
            "start_at": "2026-09-07T06:00:00+05:30",
            "end_at": "2026-09-07T06:30:00+05:30",
            "source": "existing",
        },
    ]
    out = apply_day_rhythm(blocks, day=day)
    first = out[0]
    assert "Bible" in str(first.get("title")) or first.get("category") == "spiritual"

