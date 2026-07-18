"""Tests for planner blocks — remaining time, roll-forward, effective focus."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.behavior.category_scores import (
    PRODUCTIVE_THRESHOLD,
    load_score_map,
    score_for_category,
    seed_category_scores,
)
from backend.db.base import Base
from backend.models.planner import PlannerBlock
from backend.models.timetable import TrackedSession
from backend.models.user import User
from backend.planner.effective_focus import (
    effective_focus_minutes,
    plan_adherence_pct,
    productive_minutes_from_sessions,
)
from backend.planner.service import complete_block, roll_forward_block, suggest_next_slot


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    user = User(id=1, username="planner_test", password_hash="x")
    session.add(user)
    session.commit()
    seed_category_scores(session)
    yield session
    session.close()


def _block(session, user_id: int = 1, **kwargs) -> PlannerBlock:
    now = datetime.now(timezone.utc)
    defaults = dict(
        user_id=user_id,
        title="Reading",
        category="reading",
        start_at=now,
        end_at=now + timedelta(minutes=60),
        planned_minutes=60,
        remaining_minutes=60,
        status="scheduled",
    )
    defaults.update(kwargs)
    b = PlannerBlock(**defaults)
    session.add(b)
    session.flush()
    return b


def _session(db, *, start, end, category: str, sid: str = "sess-1") -> TrackedSession:
    row = TrackedSession(
        session_id=sid,
        user_id=1,
        start_time=start,
        end_time=end,
        source="desktop_tracker",
        category=category,
    )
    db.add(row)
    db.flush()
    return row


def test_complete_partial_reduces_remaining(db_session):
    block = _block(db_session)
    complete_block(block, minutes_spent=20)
    assert block.remaining_minutes == 40
    assert block.status == "scheduled"


def test_complete_full_marks_done(db_session):
    block = _block(db_session)
    complete_block(block, minutes_spent=60)
    assert block.remaining_minutes == 0
    assert block.status == "done"


def test_roll_forward_preserves_remaining(db_session):
    block = _block(db_session)
    complete_block(block, minutes_spent=20)
    new = roll_forward_block(db_session, block)
    assert block.status == "rolled"
    assert new.remaining_minutes == 40
    assert new.planned_minutes == 60
    assert new.rolled_from_id == block.id
    assert new.roll_count == 1


def test_suggest_next_slot_avoids_overlap(db_session):
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    _block(
        db_session,
        start_at=now + timedelta(hours=1),
        end_at=now + timedelta(hours=2),
        planned_minutes=60,
        remaining_minutes=60,
    )
    slot = suggest_next_slot(db_session, 1, after=now, duration_minutes=30)
    assert slot >= now + timedelta(hours=2)


def test_effective_focus_minutes_inside_planned_block(db_session):
    day = datetime(2026, 7, 7, 0, 0, 0, tzinfo=timezone.utc)
    block = _block(
        db_session,
        start_at=day.replace(hour=10),
        end_at=day.replace(hour=11),
        planned_minutes=60,
        remaining_minutes=60,
    )
    session = _session(
        db_session,
        start=day.replace(hour=10, minute=30),
        end=day.replace(hour=10, minute=45),
        category="IDE / Code Editor",
    )
    db_session.commit()

    scores = load_score_map(db_session)
    score_fn = lambda cat: score_for_category(cat, scores)

    assert effective_focus_minutes([block], [session], score_fn) == 15


def test_plan_adherence_uses_effective_focus_not_raw_screen_time():
    """370%-style bugs: raw tracked >> planned must not inflate adherence."""
    assert plan_adherence_pct(effective_focus=15, planned_minutes=60) == 25.0
    assert plan_adherence_pct(effective_focus=60, planned_minutes=60) == 100.0
    # Cap — even if caller passes nonsense
    assert plan_adherence_pct(effective_focus=200, planned_minutes=60) == 100.0
    assert plan_adherence_pct(effective_focus=0, planned_minutes=60) == 0.0
    assert plan_adherence_pct(effective_focus=10, planned_minutes=0) is None


def test_effective_focus_zero_when_below_threshold(db_session):
    day = datetime(2026, 7, 7, 0, 0, 0, tzinfo=timezone.utc)
    block = _block(
        db_session,
        start_at=day.replace(hour=10),
        end_at=day.replace(hour=11),
        planned_minutes=60,
        remaining_minutes=60,
    )
    session = _session(
        db_session,
        start=day.replace(hour=10, minute=30),
        end=day.replace(hour=10, minute=45),
        category="Video Streaming",
    )
    db_session.commit()

    scores = load_score_map(db_session)
    score_fn = lambda cat: score_for_category(cat, scores)

    assert effective_focus_minutes([block], [session], score_fn) == 0


def test_effective_focus_ignores_session_outside_block(db_session):
    day = datetime(2026, 7, 7, 0, 0, 0, tzinfo=timezone.utc)
    block = _block(
        db_session,
        start_at=day.replace(hour=10),
        end_at=day.replace(hour=11),
        planned_minutes=60,
        remaining_minutes=60,
    )
    session = _session(
        db_session,
        start=day.replace(hour=12),
        end=day.replace(hour=12, minute=30),
        category="IDE / Code Editor",
    )
    db_session.commit()

    scores = load_score_map(db_session)
    score_fn = lambda cat: score_for_category(cat, scores)

    assert effective_focus_minutes([block], [session], score_fn) == 0


def test_productive_minutes_uses_threshold_60(db_session):
    day = datetime(2026, 7, 7, 0, 0, 0, tzinfo=timezone.utc)
    high = _session(
        db_session,
        start=day.replace(hour=9),
        end=day.replace(hour=9, minute=30),
        category="IDE / Code Editor",
        sid="high",
    )
    low = _session(
        db_session,
        start=day.replace(hour=9, minute=30),
        end=day.replace(hour=10),
        category="Communication",
        sid="low",
    )
    borderline = _session(
        db_session,
        start=day.replace(hour=10),
        end=day.replace(hour=10, minute=20),
        category="Email / Calendar",
        sid="border",
    )
    db_session.commit()

    scores = load_score_map(db_session)
    score_fn = lambda cat: score_for_category(cat, scores)

    productive = productive_minutes_from_sessions([high, low, borderline], score_fn)
    assert PRODUCTIVE_THRESHOLD == 60
    assert score_for_category("Communication", scores) < PRODUCTIVE_THRESHOLD
    assert score_for_category("Email / Calendar", scores) < PRODUCTIVE_THRESHOLD
    assert productive == 30
