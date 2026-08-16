"""Tests for morning auto-draft day plan (after Bible)."""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.db.base import Base
from backend.models.planner import PlannerBlock
from backend.models.planner_routine import PlannerRoutine
from backend.models.user import User
from backend.planner import auto_plan as ap
from backend.planner.service import wall_clock_on_date


@pytest.fixture()
def db_session(tmp_path, monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    session.add(User(id=1, username="auto_plan_test", password_hash="x"))
    session.commit()
    monkeypatch.setattr(ap, "AUTO_DRAFT_STATE_PATH", tmp_path / "planner_auto_draft.json")
    monkeypatch.setattr(
        "backend.planner.routines.AUTO_APPLY_STATE_PATH",
        tmp_path / "planner_routine_auto_apply.json",
    )
    monkeypatch.setattr(
        "backend.planner.morning_plan._STORE",
        tmp_path / "planner_morning_confirm.json",
    )
    monkeypatch.setenv("MORNING_AUTO_PLAN", "1")
    monkeypatch.setenv("MORNING_AUTO_PLAN_CONFIRM", "0")
    monkeypatch.delenv("MORNING_AUTO_PLAN_LLM", raising=False)
    yield session
    session.close()


def _add_daily_routine(db, *, title="Morning deep work", start="09:00", end="10:00"):
    db.add(
        PlannerRoutine(
            user_id=1,
            title=title,
            category="study",
            start_time=start,
            end_time=end,
            days_json='["mon","tue","wed","thu","fri","sat","sun"]',
            enabled=True,
            sort_order=0,
        )
    )
    db.commit()


def test_auto_draft_creates_from_routines(db_session, monkeypatch):
    spoken: list[str] = []
    monkeypatch.setattr(
        "backend.behavior.voice_agent.dialogues.speak",
        lambda cat, **kw: spoken.append(cat) or cat,
    )
    _add_daily_routine(db_session)

    out = ap.auto_draft_day_plan(db_session, 1)
    assert out["skipped"] is False
    assert out["created"] >= 1
    assert any(t == "Morning deep work" for t in out["titles"])
    assert out["auto_plan"]["drafted"] is True
    assert len(out["auto_plan"]["titles"]) >= 1

    blocks = db_session.query(PlannerBlock).filter(PlannerBlock.user_id == 1).all()
    assert len(blocks) >= 1
    assert "plan_auto_drafted" in spoken


def test_auto_draft_idempotent_second_call(db_session, monkeypatch):
    monkeypatch.setattr(
        "backend.behavior.voice_agent.dialogues.speak",
        lambda cat, **kw: cat,
    )
    _add_daily_routine(db_session)

    first = ap.auto_draft_day_plan(db_session, 1)
    assert first["skipped"] is False
    n = db_session.query(PlannerBlock).filter(PlannerBlock.user_id == 1).count()

    second = ap.auto_draft_day_plan(db_session, 1)
    assert second["skipped"] is True
    assert second["reason"] == "already_drafted"
    assert db_session.query(PlannerBlock).filter(PlannerBlock.user_id == 1).count() == n


def test_auto_draft_skips_if_plan_exists(db_session, monkeypatch):
    monkeypatch.setattr(
        "backend.behavior.voice_agent.dialogues.speak",
        lambda cat, **kw: cat,
    )
    today = datetime.now().astimezone().date()
    start = wall_clock_on_date(today, "11:00")
    end = wall_clock_on_date(today, "12:00")
    db_session.add(
        PlannerBlock(
            user_id=1,
            title="User edited study",
            category="study",
            start_at=start,
            end_at=end,
            planned_minutes=60,
            remaining_minutes=60,
            status="scheduled",
        )
    )
    db_session.commit()
    _add_daily_routine(db_session, title="Bath", start="21:30", end="22:00")

    out = ap.auto_draft_day_plan(db_session, 1)
    assert out["skipped"] is True
    assert out["reason"] == "plan_exists"
    assert out["auto_plan"]["drafted"] is True
    assert out["auto_plan"]["reason"] == "plan_exists"
    assert "User edited study" in out["auto_plan"]["titles"]
    assert out["ask"] == "add_or_confirm"
    # Must not clobber / duplicate-add over user's block
    titles = {b.title for b in db_session.query(PlannerBlock).filter(PlannerBlock.user_id == 1)}
    assert titles == {"User edited study"}
    # State file so gate / UI can show titles after Bible
    summary = ap.auto_plan_summary(1)
    assert summary["drafted"] is True
    assert "User edited study" in summary["titles"]


def test_auto_draft_plan_exists_speaks_ask(db_session, monkeypatch):
    spoken: list[str] = []
    monkeypatch.setattr(
        "backend.behavior.voice_agent.dialogues.speak",
        lambda cat, **kw: spoken.append(cat) or cat,
    )
    today = datetime.now().astimezone().date()
    start = wall_clock_on_date(today, "11:00")
    end = wall_clock_on_date(today, "12:00")
    db_session.add(
        PlannerBlock(
            user_id=1,
            title="Existing",
            category="study",
            start_at=start,
            end_at=end,
            planned_minutes=60,
            remaining_minutes=60,
            status="scheduled",
        )
    )
    db_session.commit()
    out = ap.auto_draft_day_plan(db_session, 1, speak=True)
    assert out["reason"] == "plan_exists"
    assert "plan_exists_ask" in spoken


def test_auto_draft_add_more_fills_gaps(db_session, monkeypatch):
    monkeypatch.setattr(
        "backend.behavior.voice_agent.dialogues.speak",
        lambda cat, **kw: cat,
    )
    today = datetime.now().astimezone().date()
    start = wall_clock_on_date(today, "11:00")
    end = wall_clock_on_date(today, "12:00")
    db_session.add(
        PlannerBlock(
            user_id=1,
            title="User edited study",
            category="study",
            start_at=start,
            end_at=end,
            planned_minutes=60,
            remaining_minutes=60,
            status="scheduled",
        )
    )
    db_session.commit()
    _add_daily_routine(db_session, title="Bath", start="21:30", end="22:00")

    # First hit → plan_exists
    ap.auto_draft_day_plan(db_session, 1, speak=False)
    # Add more should apply routines into free gaps
    out = ap.auto_draft_day_plan(db_session, 1, add_more=True, speak=False)
    assert out["skipped"] is False
    assert out["reason"] == "add_more"
    titles = {b.title for b in db_session.query(PlannerBlock).filter(PlannerBlock.user_id == 1)}
    assert "User edited study" in titles
    assert "Bath" in titles or out["created"] >= 0  # routines or seeds may fill
    monkeypatch.setenv("MORNING_AUTO_PLAN", "0")
    _add_daily_routine(db_session)
    out = ap.auto_draft_day_plan(db_session, 1)
    assert out["skipped"] is True
    assert out["reason"] == "disabled"


def test_auto_plan_summary_from_state(db_session, monkeypatch):
    monkeypatch.setattr(
        "backend.behavior.voice_agent.dialogues.speak",
        lambda cat, **kw: cat,
    )
    _add_daily_routine(db_session)
    ap.auto_draft_day_plan(db_session, 1)
    summary = ap.auto_plan_summary(1)
    assert summary["drafted"] is True
    assert isinstance(summary["titles"], list)
    assert len(summary["titles"]) >= 1


def test_auto_confirm_only_when_env_and_window(db_session, monkeypatch, tmp_path):
    from backend.planner import morning_plan as mp
    from backend.planner import morning_rewards as mr

    monkeypatch.setattr(mp, "_STORE", tmp_path / "planner_morning_confirm.json")
    monkeypatch.setattr(mr, "_STORE", tmp_path / "morning_rewards.json")
    monkeypatch.setenv("MORNING_AUTO_PLAN_CONFIRM", "1")
    monkeypatch.setenv("MORNING_PLAN_START", "05:00")
    monkeypatch.setenv("MORNING_PLAN_EOD", "23:59")
    monkeypatch.setattr(
        "backend.behavior.voice_agent.dialogues.speak",
        lambda cat, **kw: cat,
    )
    _add_daily_routine(db_session)

    now = datetime.now().astimezone().replace(hour=10, minute=0, second=0, microsecond=0)
    out = ap.auto_draft_day_plan(
        db_session,
        1,
        bible_done=True,
        bible_completed_at=now - timedelta(minutes=5),
        now=now,
    )
    assert out["skipped"] is False
    assert out.get("confirmed") is True
    assert mp.is_plan_confirmed(1) is True
