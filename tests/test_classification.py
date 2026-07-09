"""Tests for LLM classification backfill (exe + domain keys)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.behavior.category_scores import seed_category_scores
from backend.behavior.classification_service import (
    backfill_approved,
    normalize_title_key,
    preview_impact,
    revert_backfill,
)
from backend.db.base import Base
from backend.models.timetable import TrackedSession
from backend.models.user import User


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    user = User(id=1, username="classify_test", password_hash="x")
    session.add(user)
    session.commit()
    seed_category_scores(session)
    yield session
    session.close()


def _row(
    db,
    *,
    app_name: str,
    category: str,
    title: str | None = None,
    category_source: str | None = None,
    suffix: str = "",
) -> TrackedSession:
    start = datetime.now(UTC) - timedelta(minutes=10)
    end = datetime.now(UTC)
    row = TrackedSession(
        session_id=f"s-{app_name}-{title or 'x'}-{suffix}",
        user_id=1,
        start_time=start,
        end_time=end,
        source="desktop_tracker",
        category=category,
        app_name=app_name,
        window_title=title,
        category_source=category_source,
    )
    db.add(row)
    db.commit()
    return row


def test_normalize_title_key_strips_browser_suffix():
    assert normalize_title_key("GitHub - Google Chrome") == "GitHub"
    assert normalize_title_key("Docs - Microsoft Edge") == "Docs"


def test_backfill_exe_updates_other_sessions(db_session):
    _row(db_session, app_name="foo.exe", category="Other", suffix="1")
    _row(db_session, app_name="foo.exe", category="Other", suffix="2")
    _row(db_session, app_name="bar.exe", category="Other", suffix="3")

    affected = backfill_approved(db_session, "foo.exe", "exe", "Dev Tools")
    db_session.commit()

    assert affected == 2
    cats = [r.category for r in db_session.query(TrackedSession).filter(TrackedSession.app_name == "foo.exe")]
    assert cats == ["Dev Tools", "Dev Tools"]
    assert db_session.query(TrackedSession).filter(TrackedSession.app_name == "bar.exe").one().category == "Other"


def test_backfill_domain_updates_browser_sessions(db_session):
    title = "Stack Overflow - Google Chrome"
    key = normalize_title_key(title)
    _row(db_session, app_name="chrome.exe", category="Browser", title=title, suffix="1")
    _row(db_session, app_name="chrome.exe", category="Browser", title=title, suffix="2")
    _row(db_session, app_name="chrome.exe", category="Browser", title="Other site - Chrome", suffix="3")

    affected = backfill_approved(db_session, key, "domain", "Study (Browser)")
    db_session.commit()

    assert affected == 2
    updated = db_session.query(TrackedSession).filter(TrackedSession.window_title == title).all()
    assert all(r.category == "Study (Browser)" for r in updated)
    assert all(r.category_source == "llm_reviewed" for r in updated)


def test_preview_impact_domain_matches_normalized_title(db_session):
    title = "Coursera - Microsoft Edge"
    key = normalize_title_key(title)
    _row(db_session, app_name="msedge.exe", category="Browser", title=title)

    impact = preview_impact(db_session, key, "domain")
    assert impact["count"] == 1
    assert impact["total_minutes"] > 0


def test_revert_domain_restores_prior_category(db_session):
    title = "Notion - Google Chrome"
    key = normalize_title_key(title)
    row = _row(db_session, app_name="chrome.exe", category="Browser", title=title)
    backfill_approved(db_session, key, "domain", "Knowledge Work")
    db_session.commit()

    reverted = revert_backfill(db_session, key, "domain")
    db_session.commit()

    assert reverted == 1
    db_session.refresh(row)
    assert row.category == "Browser"
    assert row.category_source == "rule"
