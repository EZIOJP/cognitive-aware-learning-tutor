"""Native session category backfill (maturity F2)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.behavior.native_session_backfill import backfill_native_session_categories
from backend.db.base import Base
from backend.models.timetable import TrackedSession
from backend.models.user import User


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[User.__table__, TrackedSession.__table__])
    session = sessionmaker(bind=engine)()
    u = User(username="native_bf", password_hash="x")
    session.add(u)
    session.commit()
    try:
        yield session
    finally:
        session.close()


def test_backfill_sets_category_for_native_rows(db_session: Session):
    uid = int(db_session.query(User).one().id)
    now = datetime.now(timezone.utc)
    row = TrackedSession(
        session_id="native-test-1",
        user_id=uid,
        start_time=now,
        end_time=now,
        source="desktop_tracker",
        app_name="notepad.exe",
        window_title="Untitled",
        category=None,
        category_source="native",
    )
    db_session.add(row)
    db_session.commit()

    n = backfill_native_session_categories(db_session, user_id=uid, limit=10)
    assert n >= 1
    db_session.refresh(row)
    assert row.category
    assert row.category_source == "native"
