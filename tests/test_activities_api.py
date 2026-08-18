"""Tests for activities payload."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.behavior.category_scores import load_score_map, seed_category_scores
from backend.behavior.stats_aggregate import activities_payload, aggregate_session_rows
from backend.db.base import Base
from backend.models.timetable import TrackedSession
from backend.models.user import User


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    user = User(id=1, username="act_test", password_hash="x")
    session.add(user)
    session.commit()
    seed_category_scores(session)
    yield session
    session.close()


def test_activities_payload_uncategorized(db_session):
    now = datetime.now(UTC)
    row = TrackedSession(
        session_id="a1",
        user_id=1,
        start_time=now - timedelta(minutes=30),
        end_time=now,
        source="desktop_tracker",
        category="Other",
        app_name="unknown.exe",
    )
    scores = load_score_map(db_session)
    buckets, _ = aggregate_session_rows([row], scores=scores)
    items = activities_payload(buckets)
    assert len(items) == 1
    assert items[0]["uncategorized"] is True
    assert items[0]["kind"] == "app"
