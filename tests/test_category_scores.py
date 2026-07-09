"""Tests for read-time category_scores resolution."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.behavior.category_scores import (
    DEFAULT_SCORE,
    PRODUCTIVE_THRESHOLD,
    load_score_map,
    score_for_category,
    seed_category_scores,
)
from backend.behavior.router import _desktop_stats_from_tracked_sessions
from backend.db.base import Base
from backend.models.timetable import TrackedSession
from backend.models.user import User
from backend.timetable.tracker_bridge import ingest_desktop_session


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    user = User(id=1, username="score_test", password_hash="x")
    session.add(user)
    session.commit()
    seed_category_scores(session)
    yield session
    session.close()


def test_score_for_category_known_and_default(db_session):
    scores = load_score_map(db_session)
    assert score_for_category("IDE / Code Editor", scores) == 95
    assert score_for_category("Unknown Category XYZ", scores) == DEFAULT_SCORE
    assert score_for_category(None, scores) == DEFAULT_SCORE


def test_build_seed_includes_other_at_35(db_session):
    scores = load_score_map(db_session)
    assert scores["Other"] == 35
    assert scores["IDE / Code Editor"] == 95


def test_stale_score_fix_category_change_without_backfill(db_session):
    """Category update should change resolved score without touching stored score column."""
    now = datetime.now(UTC)
    row = TrackedSession(
        session_id="stale-score-1",
        user_id=1,
        start_time=now - timedelta(minutes=30),
        end_time=now,
        source="desktop_tracker",
        category="Other",
        app_name="foo.exe",
    )
    db_session.add(row)
    db_session.commit()

    scores = load_score_map(db_session)
    assert score_for_category(row.category, scores) == 35

    row.category = "IDE / Code Editor"
    db_session.commit()

    scores = load_score_map(db_session)
    assert score_for_category(row.category, scores) == 95


def test_ingest_then_resolve_via_stats(db_session):
    payload = {
        "type": "SESSION_END",
        "source": "desktop_tracker",
        "exe": "Cursor.exe",
        "title": "main.py - Cursor",
        "category": "Other",
        "duration_seconds": 120,
        "timestamp": int((datetime.now(UTC) - timedelta(minutes=2)).timestamp() * 1000),
        "end_timestamp": int(datetime.now(UTC).timestamp() * 1000),
    }
    ingested = ingest_desktop_session(db_session, user_id=1, payload=payload)
    assert ingested is not None
    ingested.category = "IDE / Code Editor"
    db_session.commit()

    stats = _desktop_stats_from_tracked_sessions(db_session, [1], datetime.now(UTC).date())
    assert stats["sessions"]
    assert stats["sessions"][0]["productivity_score"] == 95


def test_productive_threshold_constant():
    assert PRODUCTIVE_THRESHOLD == 60
