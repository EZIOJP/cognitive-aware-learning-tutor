"""Enforcer ownership handoff — UI must not kill while native owns (default)."""

from __future__ import annotations

from pathlib import Path

import backend.behavior.enforcer_ownership as own


def test_native_owns_kills_by_default(tmp_path: Path, monkeypatch):
    """DESKTOP TRACKER RULE: Python never kills unless CALT_UI_KILLS=1."""
    lock = tmp_path / "enforcer_owner.lock"
    monkeypatch.setattr(own, "LOCK_PATH", lock)
    monkeypatch.delenv("CALT_UI_KILLS", raising=False)
    monkeypatch.delenv("CALT_ENFORCER_OWNS_KILLS", raising=False)
    assert own.enforcer_owns_kills() is True
    own.claim_ownership(pid=12345)
    assert own.enforcer_owns_kills() is True
    own.release_ownership()
    assert own.enforcer_owns_kills() is True


def test_tracking_still_needs_fresh_lock(tmp_path: Path, monkeypatch):
    lock = tmp_path / "enforcer_owner.lock"
    monkeypatch.setattr(own, "LOCK_PATH", lock)
    monkeypatch.delenv("CALT_UI_KILLS", raising=False)
    monkeypatch.delenv("CALT_ENFORCER_OWNS_KILLS", raising=False)
    assert own.enforcer_owns_tracking() is False
    own.claim_ownership(pid=99)
    assert own.enforcer_owns_tracking() is True
    own.release_ownership()
    assert own.enforcer_owns_tracking() is False


def test_ui_kills_env_overrides(tmp_path: Path, monkeypatch):
    lock = tmp_path / "enforcer_owner.lock"
    monkeypatch.setattr(own, "LOCK_PATH", lock)
    own.claim_ownership(pid=1)
    monkeypatch.setenv("CALT_UI_KILLS", "1")
    assert own.enforcer_owns_kills() is False
