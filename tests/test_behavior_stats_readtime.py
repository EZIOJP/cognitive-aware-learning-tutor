"""Regression tests for read-time score API paths that previously 500'd."""

from __future__ import annotations

import csv
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.behavior.category_scores import (
    load_score_map,
    seed_category_scores,
    serialize_session,
)
from backend.behavior.router import _browser_stats_from_desktop_csv
from backend.db.base import Base
from backend.main import app
from backend.models.timetable import TrackedSession
from backend.models.user import User

client = TestClient(app)


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    user = User(id=1, username="api_score_test", password_hash="x")
    session.add(user)
    session.commit()
    seed_category_scores(session)
    yield session
    session.close()


def test_serialize_session_alias_matches_tracked_session(db_session):
    now = datetime.now(UTC)
    row = TrackedSession(
        session_id="alias-1",
        user_id=1,
        start_time=now - timedelta(minutes=10),
        end_time=now,
        source="desktop_tracker",
        category="IDE / Code Editor",
        app_name="code.exe",
    )
    scores = load_score_map(db_session)
    payload = serialize_session(row, scores)
    assert payload["productivity_score"] == 95
    assert payload["category"] == "IDE / Code Editor"


def test_browser_stats_from_desktop_csv_with_scores(tmp_path, monkeypatch):
    """CSV fallback path must pass scores into aggregate_session_rows."""
    day = datetime.now(UTC).date()
    day_str = day.isoformat()
    csv_path = tmp_path / f"DSC_desktop_behavior_{day_str}.csv"
    start_ms = int((datetime.now(UTC) - timedelta(minutes=30)).timestamp() * 1000)
    end_ms = int(datetime.now(UTC).timestamp() * 1000)

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["timestamp", "end_timestamp", "exe", "title", "domain", "category"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "timestamp": start_ms,
                "end_timestamp": end_ms,
                "exe": "chrome.exe",
                "title": "LeetCode - Google Chrome",
                "domain": "leetcode.com",
                "category": "Coding Practice",
            }
        )

    monkeypatch.setattr("backend.behavior.router.LOG_DIR", tmp_path)

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    seed_category_scores(session)
    scores = load_score_map(session)
    session.close()

    result = _browser_stats_from_desktop_csv(day_str, scores=scores)
    assert result is not None
    assert result["events_today"] > 0
    assert result["domains"]
    assert result["domains"][0]["productivity_score"] == 90


def test_behavior_stats_endpoint_returns_200():
    r = client.get("/api/behavior/stats")
    assert r.status_code == 200
    data = r.json()
    assert "events_today" in data
    assert "domains" in data


def test_overlay_actual_endpoint_returns_200():
    now = datetime.now(UTC)
    from_dt = (now - timedelta(hours=1)).isoformat()
    to_dt = (now + timedelta(hours=1)).isoformat()
    r = client.get("/api/planner/overlay/actual", params={"from": from_dt, "to": to_dt})
    assert r.status_code == 200
    body = r.json()
    assert "sessions" in body
    assert isinstance(body["sessions"], list)
    assert "hour_slices" in body
    assert isinstance(body["hour_slices"], list)
