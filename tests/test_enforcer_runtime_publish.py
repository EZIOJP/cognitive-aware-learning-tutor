"""enforcer_policy.json publish — SoftLand does not overwrite Focus OS arm."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.behavior.enforcer_runtime_publish import publish_enforcer_runtime
from backend.db.base import Base
from backend.models.user import User


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[User.__table__])
    session = sessionmaker(bind=engine)()
    u = User(username="enforcer_test", password_hash="x")
    session.add(u)
    session.commit()
    try:
        yield session
    finally:
        session.close()


def test_publish_seeds_then_preserves_focus_arm(db_session: Session, tmp_path, monkeypatch):
    import backend.behavior.enforcer_files as ef

    monkeypatch.setattr(ef, "BEHAVIOR_DIR", tmp_path)
    monkeypatch.setattr(ef, "POLICY_PATH", tmp_path / "enforcer_policy.json")

    uid = int(db_session.query(User).one().id)
    # First publish seeds DISARMED — SoftLand never arms OS kills
    publish_enforcer_runtime(
        db_session,
        uid,
        gate={"enabled": True, "locked": True, "incubation": {"active": False}},
        policy={"hard_block_enabled": True, "hard_block_exes": ["steam.exe"]},
    )
    got = ef.read_policy_file()
    assert got is not None
    assert got["hard_block_armed"] is False
    assert got["gate_locked"] is False
    assert "steam.exe" in got["exes"]

    # Focus arms a different list
    ef.write_policy_file(
        hard_block_armed=True,
        gate_locked=True,
        exes=["notepad.exe"],
        note="focus_ui",
    )

    # SoftLand "disarms" must NOT clear Focus OS arm / kill list
    publish_enforcer_runtime(
        db_session,
        uid,
        gate={"enabled": False, "locked": False, "incubation": {"active": True}},
        policy={"hard_block_enabled": False, "hard_block_exes": ["discord.exe"]},
    )
    got2 = ef.read_policy_file()
    assert got2 is not None
    assert got2["hard_block_armed"] is True
    assert got2["gate_locked"] is True
    assert got2["exes"] == ["notepad.exe"]
    assert got2["incubation_active"] is True
