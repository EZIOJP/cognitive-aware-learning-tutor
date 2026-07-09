"""Tests for smart JSON extraction and timetable import parsing."""

from datetime import timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.db.base import Base
from backend.models.user import User
from backend.timetable.json_extract import extract_json_from_text
from backend.timetable.schemas import ImportJsonPayload


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    session.add(User(id=1, username="import_test", password_hash="x"))
    session.commit()
    yield session
    session.close()


def test_extract_from_markdown_fence():
    text = """Here is your schedule:
```json
{"type": "daily", "daily_slots": [{"start": "07:00", "end": "07:30", "title": "Bible"}]}
```
Hope this helps!"""
    data = extract_json_from_text(text)
    assert data["type"] == "daily"
    assert len(data["daily_slots"]) == 1


def test_extract_with_leading_prose():
    text = 'Sure! {"name": "Week", "slots": [{"day": "mon", "start": "09:00", "end": "10:00", "task_index": 0}]}'
    data = extract_json_from_text(text)
    assert data["name"] == "Week"


def test_import_daily_payload():
    raw = {
        "type": "daily",
        "date": "2026-07-03",
        "daily_slots": [
            {"start": "08:00", "end": "08:30", "title": "Breakfast", "category": "food"},
        ],
    }
    parsed = ImportJsonPayload.from_raw(raw)
    assert parsed.schedule_type == "daily"
    assert len(parsed.daily_slots) == 1
    assert parsed.daily_slots[0].title == "Breakfast"


def test_import_empty_raises():
    with pytest.raises(ValueError):
        extract_json_from_text("   ")


def test_slots_to_planner_blocks_daily_date(db_session):
    from datetime import date

    from backend.models.planner import PlannerBlock
    from backend.planner.routines import slots_to_planner_blocks
    from backend.planner.service import wall_clock_on_date

    blocks = slots_to_planner_blocks(
        db_session,
        1,
        [{"start": "08:30", "end": "09:00", "title": "Breakfast", "category": "food"}],
        target_date=date(2026, 7, 4),
    )
    assert len(blocks) == 1
    assert blocks[0].title == "Breakfast"
    row = db_session.query(PlannerBlock).one()
    expected = wall_clock_on_date(date(2026, 7, 4), "08:30")
    assert row.start_at.replace(tzinfo=timezone.utc) == expected.replace(tzinfo=timezone.utc)
