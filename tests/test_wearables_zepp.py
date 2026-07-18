"""Wearables full-dump + sleep load soft tests."""

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.db.base import Base
from backend.models.user import User
from backend.models.wearable_daily import WearableDaily
from backend.wearables.ingest_service import (
    sleep_load_scale_for_user,
    upsert_wearable_daily,
)
from backend.wearables.router import (
    ActivityIn,
    SleepIn,
    normalize_sleep_hours,
    score_to_quality,
    upsert_activity_from_wearable,
    upsert_sleep_from_wearable,
)


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    user = User(id=1, username="wear_full", password_hash="x", is_admin=True)
    session.add(user)
    session.commit()
    yield session
    session.close()


def test_score_to_quality():
    assert score_to_quality(82) == 4
    assert score_to_quality(None) == 3


def test_normalize_sleep_hours():
    assert normalize_sleep_hours(410) == pytest.approx(6.83, abs=0.02)
    assert normalize_sleep_hours(None) is None


def test_full_snapshot_upsert(db_session):
    user = db_session.query(User).first()
    out = upsert_wearable_daily(
        db_session,
        user,
        date(2026, 7, 18),
        {
            "sleep": {"total_min": 420, "score": 80, "deep_min": 90},
            "activity": {"steps": 6543, "target": 8000},
            "calorie": {"kcal": 512, "target": 600},
            "distance": {"meters": 4200},
            "heart": {"last": 72, "resting": 58},
            "spo2": {"value": 97},
            "stress": {"value": 42},
            "pai": {"today": 12.5, "total": 88},
            "stand": {"hours": 8, "target": 12},
            "battery": {"pct": 64},
        },
        source="mini_program",
    )
    assert out["upserted"] is True
    assert out["steps"] == 6543
    assert out["calories"] == 512
    assert out["spo2"] == 97
    assert out["exercise_minutes"] == 65
    assert out["outdoor_minutes"] == 52
    row = (
        db_session.query(WearableDaily)
        .filter(WearableDaily.user_id == user.id, WearableDaily.local_date == date(2026, 7, 18))
        .one()
    )
    assert row.pai_today == 12.5
    assert row.battery_pct == 64


def test_sleep_load_scale(db_session):
    user = db_session.query(User).first()
    upsert_wearable_daily(
        db_session,
        user,
        date.today(),
        {"sleep": {"total_min": 280, "score": 50}},
        source="mini_program",
    )
    scale, meta = sleep_load_scale_for_user(db_session, user.id)
    assert scale == 0.8
    assert meta and meta["sleep_hours"] == pytest.approx(4.67, abs=0.02)


def test_legacy_helpers(db_session):
    user = db_session.query(User).first()
    out = upsert_sleep_from_wearable(
        db_session, user, date(2026, 7, 18), SleepIn(total_min=410, score=82)
    )
    assert out["upserted"] is True
    out2 = upsert_activity_from_wearable(
        db_session, user, date(2026, 7, 18), ActivityIn(steps=1000)
    )
    assert out2["steps"] == 1000
