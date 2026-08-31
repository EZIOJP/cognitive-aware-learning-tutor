"""Smoke tests for CALT Desktop shell (no live tracker)."""

from __future__ import annotations

import os

import pytest

pytest.importorskip("PySide6")


def test_calt_desktop_version() -> None:
    from backend.behavior.calt_desktop import __version__

    assert __version__


def test_rules_policy_helpers_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    """load/save helpers call productivity_policy with a session."""
    from backend.behavior.calt_desktop.tabs import rules as rules_mod

    calls: list[tuple] = []

    class _DB:
        def close(self) -> None:
            pass

    def fake_session():
        return _DB()

    def fake_load(db, user_id):
        calls.append(("load", user_id))
        return {"hard_block_enabled": True, "daily_goal_minutes": 240, "hard_block_exes": []}

    def fake_update(db, user_id, patch):
        calls.append(("update", user_id, patch))
        return {**patch, "ok": True}

    monkeypatch.setattr("backend.db.base.SessionLocal", fake_session)
    monkeypatch.setattr(
        "backend.behavior.productivity_policy.load_policy_dict",
        fake_load,
    )
    monkeypatch.setattr(
        "backend.behavior.productivity_policy.update_policy",
        fake_update,
    )

    assert rules_mod.load_policy_for_user(1)["hard_block_enabled"] is True
    out = rules_mod.save_policy_for_user(1, {"hard_block_enabled": False})
    assert out["hard_block_enabled"] is False
    assert calls[0][0] == "load"
    assert calls[1][0] == "update"


def test_main_window_builds_offscreen() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from backend.behavior.calt_desktop.main_window import MainWindow

    app = QApplication.instance() or QApplication([])

    class _FakeService:
        user_id = 0

        def latest_gate(self, *, force: bool = False):
            return {}

        def today_seconds(self):
            return 0

    win = MainWindow(_FakeService())  # type: ignore[arg-type]
    assert win.windowTitle() == "CALT Desktop"
    win.close()
    del win
    assert app is not None
