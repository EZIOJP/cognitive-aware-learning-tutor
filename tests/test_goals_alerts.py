"""Tests for goals + alerts evaluation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.behavior.category_scores import seed_category_scores
from backend.behavior.goals_alerts import (
    build_goals_status,
    evaluate_and_fire,
    mark_fired,
    was_fired,
)
from backend.db.base import Base
from backend.models.timetable import TrackedSession
from backend.models.user import User


@pytest.fixture()
def db_session(tmp_path, monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    user = User(id=1, username="goals_test", password_hash="x")
    session.add(user)
    session.commit()
    seed_category_scores(session)

    state_path = tmp_path / "goals_alert_state.json"
    monkeypatch.setattr(
        "backend.behavior.goals_alerts._STATE_PATH",
        state_path,
    )
    queue_path = tmp_path / "pending_gate_alerts.json"
    monkeypatch.setattr(
        "backend.behavior.gate_alerts._QUEUE_PATH",
        queue_path,
    )
    yield session
    session.close()


def _add_session(db, *, score_category: str, seconds: int, app: str, site: str | None = None):
    now = datetime.now(UTC)
    row = TrackedSession(
        session_id=f"s-{app}-{seconds}",
        user_id=1,
        start_time=now - timedelta(seconds=seconds),
        end_time=now,
        source="desktop_tracker",
        category=score_category,
        app_name=site or app,
        window_title=site or app,
    )
    db.add(row)
    db.commit()


def test_build_goals_status_empty(db_session):
    from datetime import date

    status = build_goals_status(db_session, [1], date.today(), user_id=1)
    assert status["goals"][0]["met"] is False
    assert status["goals"][0]["target_seconds"] == 240 * 60


def test_goal_met_fires_once(db_session, tmp_path):
    from datetime import date

    today = date.today()
    # Productive category session — 5 hours
    _add_session(db_session, score_category="IDE / Code Editor", seconds=5 * 3600, app="code.exe")

    status = build_goals_status(db_session, [1], today, user_id=1)
    assert status["productive_seconds"] >= 4 * 3600
    assert status["goals"][0]["met"] is True

    fired = evaluate_and_fire(db_session, [1], today, user_id=1)
    assert len(fired) == 1
    assert fired[0]["id"] == "productive_daily_goal"
    assert was_fired(today, "productive_daily_goal")

    fired2 = evaluate_and_fire(db_session, [1], today, user_id=1)
    assert fired2 == []


def test_youtube_alert(db_session):
    from datetime import date

    today = date.today()
    _add_session(
        db_session,
        score_category="Video Streaming",
        seconds=2000,
        app="msedge.exe",
        site="youtube.com",
    )
    status = build_goals_status(db_session, [1], today, user_id=1)
    yt = next(a for a in status["alerts"] if a["id"] == "youtube_cap_30m")
    assert yt["triggered"] is True
