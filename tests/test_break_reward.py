"""Break / reward ledger + incubation (Desktop Tracker v2c)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.db.base import Base
from backend.models.break_reward import BreakSession, RewardLedger
from backend.behavior import break_reward as br


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


def test_empty_ledger_balance_zero(db_session):
    assert br.balance(1, db=db_session) == 0
    assert br.daily_earned(1, db=db_session) == 0


def test_models_smoke(db_session):
    row = BreakSession(
        user_id=1,
        kind=br.KIND_INCUBATION,
        started_at=datetime.now(UTC).replace(tzinfo=None),
        duration_sec=480,
        ended_at=None,
        source_session_id=None,
        payload_json="{}",
    )
    db_session.add(row)
    db_session.commit()
    assert db_session.query(BreakSession).count() == 1
    assert db_session.query(RewardLedger).count() == 0


def test_earn_spend_and_daily_cap(db_session, cfg, tmp_path, monkeypatch):
    override = tmp_path / "free.json"
    monkeypatch.setattr(
        "backend.behavior.browser_gate_policy._FREE_OVERRIDE_PATH",
        override,
    )

    r1 = br.earn(1, br.REASON_BIBLE, db=db_session, config=cfg)
    assert r1["credited"] == 15
    assert r1["balance"] == 15

    r2 = br.earn(1, br.REASON_PLAN, db=db_session, config=cfg)
    assert r2["credited"] == 10
    assert br.balance(1, db=db_session) == 25

    r3 = br.earn(1, br.REASON_DAILY_GOAL, db=db_session, config=cfg)
    assert r3["credited"] == 30
    assert br.balance(1, db=db_session) == 55
    assert br.daily_earned(1, db=db_session) == 55

    # Cap at 60 — only 5 more allowed
    r4 = br.earn(1, br.REASON_BIBLE, db=db_session, config=cfg)
    assert r4["credited"] == 5
    assert r4["capped"] is True
    assert br.balance(1, db=db_session) == 60
    assert br.daily_earned(1, db=db_session) == 60

    r5 = br.earn(1, br.REASON_PLAN, db=db_session, config=cfg)
    assert r5["credited"] == 0
    assert br.balance(1, db=db_session) == 60

    spent = br.spend(1, 20, db=db_session, apply_override=True)
    assert spent["spent"] == 20
    assert spent["balance"] == 40
    assert br.balance(1, db=db_session) == 40
    assert override.is_file()

    with pytest.raises(ValueError, match="insufficient_balance"):
        br.spend(1, 999, db=db_session, apply_override=False)


def test_incubation_blocks_pin_free_override(db_session, cfg, tmp_path, monkeypatch):
    override = tmp_path / "free.json"
    monkeypatch.setattr(
        "backend.behavior.browser_gate_policy._FREE_OVERRIDE_PATH",
        override,
    )
    # Avoid solo-owner DB: patch solo_incubation_active used by set_free_override
    started = br.start_incubation(1, db=db_session, config=cfg)
    assert started is not None
    assert started["active"] is True
    assert br.incubation_active(1, db=db_session) is True
    assert br.force_study_hard(1, db=db_session) is True

    monkeypatch.setattr(br, "solo_incubation_active", lambda **kw: True)

    from backend.behavior.browser_gate_policy import set_free_override

    with pytest.raises(br.IncubationBlocksFreeOverride):
        set_free_override(minutes=30, path=override)

    assert not override.is_file()

    # After incubation ends, PIN works again
    monkeypatch.setattr(br, "solo_incubation_active", lambda **kw: False)
    until = set_free_override(minutes=30, path=override)
    assert until is not None
    assert override.is_file()


def test_tick_closes_expired_incubation(db_session, cfg):
    past = datetime.now(UTC) - timedelta(minutes=20)
    started = br.start_incubation(1, db=db_session, now=past, config=cfg)
    assert started is not None
    # Force short duration by updating row
    row = db_session.query(BreakSession).one()
    row.duration_sec = 60
    row.started_at = (datetime.now(UTC) - timedelta(minutes=5)).replace(tzinfo=None)
    db_session.commit()

    st = br.tick_incubation(1, db=db_session)
    assert st["active"] is False
    assert br.incubation_active(1, db=db_session) is False


def test_max_one_incubation_per_hour(db_session, cfg):
    now = datetime.now(UTC)
    assert br.start_incubation(1, db=db_session, now=now, config=cfg) is not None
    # End it so we are not "already active"
    row = db_session.query(BreakSession).one()
    row.ended_at = now.replace(tzinfo=None)
    db_session.commit()

    refused = br.start_incubation(
        1, db=db_session, now=now + timedelta(minutes=10), config=cfg
    )
    assert refused is None


def test_load_config_writes_defaults(tmp_path: Path):
    path = tmp_path / "behavior" / "break_reward_config.json"
    assert not path.exists()
    cfg = br.load_config(path=path, write_defaults=True)
    assert path.is_file()
    assert cfg["work_minutes"] == 45
    assert cfg["break_minutes"] == 8
    assert cfg["daily_earn_cap"] == 60
    assert cfg["earn"][br.REASON_BIBLE] == 15
