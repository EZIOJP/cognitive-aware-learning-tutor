"""Hooks: bible/plan/daily-goal earn + focus-end → incubation (Task 6)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.db.base import Base
from backend.models.break_reward import BreakSession, RewardLedger
from backend.behavior import break_reward as br
from backend.behavior import break_reward_hooks as hooks


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[BreakSession.__table__, RewardLedger.__table__])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def cfg() -> dict:
    return {
        "work_minutes": 45,
        "break_minutes": 8,
        "max_incubations_per_hour": 1,
        "allow_snooze": False,
        "earn": {
            br.REASON_BIBLE: 15,
            br.REASON_PLAN: 10,
            br.REASON_DAILY_GOAL: 30,
        },
        "daily_earn_cap": 60,
    }


def test_earn_once_bible_and_plan_idempotent(db_session, cfg):
    r1 = hooks.on_bible_done(1, db=db_session, config=cfg)
    assert r1 is not None
    assert r1["credited"] == 15
    assert r1["balance"] == 15

    r1b = hooks.on_bible_done(1, db=db_session, config=cfg)
    assert r1b is not None
    assert r1b["credited"] == 0
    assert r1b.get("already") is True
    assert br.balance(1, db=db_session) == 15

    r2 = hooks.on_plan_confirm(1, db=db_session, config=cfg)
    assert r2 is not None
    assert r2["credited"] == 10
    assert br.balance(1, db=db_session) == 25

    r2b = hooks.on_plan_confirm(1, db=db_session, config=cfg)
    assert r2b["credited"] == 0
    assert br.balance(1, db=db_session) == 25


def test_maybe_earn_daily_goal_once(db_session, cfg):
    miss = hooks.maybe_earn_daily_goal(
        1, productive_minutes=100, daily_goal_minutes=240, db=db_session, config=cfg
    )
    assert miss is None

    hit = hooks.maybe_earn_daily_goal(
        1, productive_minutes=240, daily_goal_minutes=240, db=db_session, config=cfg
    )
    assert hit is not None
    assert hit["credited"] == 30

    again = hooks.maybe_earn_daily_goal(
        1, productive_minutes=300, daily_goal_minutes=240, db=db_session, config=cfg
    )
    assert again is not None
    assert again["credited"] == 0


def test_maybe_start_incubation_after_focus_study_block(db_session, cfg):
    started = hooks.maybe_start_incubation_after_focus(
        1,
        trigger="study_block_end",
        source_session_id="block-42",
        db=db_session,
        config=cfg,
    )
    assert started is not None
    assert started["active"] is True
    assert br.incubation_active(1, db=db_session) is True


def test_maybe_start_incubation_after_focus_streak_threshold(db_session, cfg):
    too_short = hooks.maybe_start_incubation_after_focus(
        1,
        trigger="productive_streak",
        productive_streak_min=30,
        db=db_session,
        config=cfg,
    )
    assert too_short is None

    ok = hooks.maybe_start_incubation_after_focus(
        1,
        trigger="productive_streak",
        productive_streak_min=45,
        source_session_id="streak",
        db=db_session,
        config=cfg,
    )
    assert ok is not None
    assert ok["active"] is True

    # Rate limit: end and refuse second within hour
    row = db_session.query(BreakSession).one()
    row.ended_at = datetime.now(UTC).replace(tzinfo=None)
    db_session.commit()

    refused = hooks.maybe_start_incubation_after_focus(
        1,
        trigger="productive_streak",
        productive_streak_min=50,
        db=db_session,
        config=cfg,
        now=datetime.now(UTC) + timedelta(minutes=5),
    )
    assert refused is None


def test_maybe_start_incubation_ignores_unknown_trigger(db_session, cfg):
    assert (
        hooks.maybe_start_incubation_after_focus(
            1, trigger="nope", db=db_session, config=cfg
        )
        is None
    )


def test_morning_rewards_grant_calls_hook(monkeypatch, tmp_path):
    """grant(bible) invokes on_bible_done once when newly awarded."""
    store = tmp_path / "morning_rewards.json"
    monkeypatch.setattr("backend.planner.morning_rewards._STORE", store)
    calls: list[int] = []

    def _capture(uid, **_kw):
        calls.append(int(uid))
        return {"credited": 15, "reason": br.REASON_BIBLE}

    monkeypatch.setattr(
        "backend.behavior.break_reward_hooks.on_bible_done",
        _capture,
    )
    from backend.planner import morning_rewards as mr

    mr.grant(7, "bible")
    mr.grant(7, "bible")  # idempotent morning award — no second hook
    assert calls == [7]
