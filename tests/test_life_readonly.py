"""Life Tracker: manual edits disabled; wearable-owned fields blocked on PUT."""

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.db.base import Base
from backend.life.router import put_life_daily
from backend.life.schemas import LifeDailyIn
from backend.models.user import User
from fastapi import HTTPException


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    user = User(id=1, username="life_ro", password_hash="x", is_admin=True)
    session.add(user)
    session.commit()
    yield session
    session.close()


def test_put_rejects_sleep_manual(db_session):
    user = db_session.query(User).first()
    with pytest.raises(HTTPException) as ei:
        put_life_daily(
            "today",
            LifeDailyIn(sleep_hours=8.0),
            db=db_session,
            user=user,
        )
    assert ei.value.status_code == 403


def test_put_allows_study_minutes(db_session):
    user = db_session.query(User).first()
    out = put_life_daily(
        "today",
        LifeDailyIn(study_minutes=50),
        db=db_session,
        user=user,
    )
    assert out["manual_edit"] is False
    assert out["log"]["study_minutes"] == 50
    from backend.models import LifeDailyLog

    row = (
        db_session.query(LifeDailyLog)
        .filter(LifeDailyLog.user_id == user.id, LifeDailyLog.date == date.today())
        .one()
    )
    assert row.study_minutes == 50
    # sleep untouched / default
    assert (row.sleep_hours or 0) == 0
