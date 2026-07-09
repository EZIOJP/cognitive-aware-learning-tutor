"""Tests for planner routines — local wall clock and auto-apply."""

from datetime import date, datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.db.base import Base
from backend.models.planner_routine import PlannerRoutine
from backend.models.user import User
from backend.planner.routines import auto_apply_routines_today, apply_routines
from backend.planner.service import wall_clock_on_date


@pytest.fixture()
def db_session(tmp_path, monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    session.add(User(id=1, username="routine_test", password_hash="x"))
    session.commit()
    state_path = tmp_path / "auto_apply.json"
    monkeypatch.setattr(
        "backend.planner.routines.AUTO_APPLY_STATE_PATH",
        state_path,
    )
    yield session
    session.close()


def test_wall_clock_on_date_uses_local_intent():
    utc = wall_clock_on_date(date(2026, 7, 4), "21:30")
    local = utc.astimezone()
    assert local.hour == 21
    assert local.minute == 30
    assert local.date() == date(2026, 7, 4)


def test_auto_apply_routines_once_per_day(db_session):
    db_session.add(
        PlannerRoutine(
            user_id=1,
            title="Bath",
            category="personal",
            start_time="21:30",
            end_time="22:00",
            days_json='["mon","tue","wed","thu","fri","sat","sun"]',
            enabled=True,
            sort_order=0,
        )
    )
    db_session.commit()

    first = auto_apply_routines_today(db_session, 1)
    assert first["skipped"] is False
    assert first["created"] == 1

    second = auto_apply_routines_today(db_session, 1)
    assert second["skipped"] is True
    assert second["created"] == 0


def test_apply_routines_skip_overlaps(db_session):
    db_session.add(
        PlannerRoutine(
            user_id=1,
            title="Breakfast",
            category="food",
            start_time="08:00",
            end_time="08:30",
            days_json='["daily"]',
            enabled=True,
            sort_order=0,
        )
    )
    db_session.commit()

    created = apply_routines(db_session, 1, target_date=datetime.now().astimezone().date())
    assert len(created) == 1
    again = apply_routines(db_session, 1, target_date=datetime.now().astimezone().date())
    assert len(again) == 0
