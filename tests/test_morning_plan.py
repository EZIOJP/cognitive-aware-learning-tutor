"""Unit tests for morning plan confirm store."""

from pathlib import Path

import pytest

from backend.planner import morning_plan as mp


def test_confirm_plan_today_roundtrip(tmp_path, monkeypatch):
    store = tmp_path / "planner_morning_confirm.json"
    monkeypatch.setattr(mp, "_STORE", store)
    assert mp.is_plan_confirmed(1) is False
    out = mp.confirm_plan_today(1, goals="Study Scaler today", skip_window_check=True)
    assert out["ok"] is True
    assert mp.is_plan_confirmed(1) is True
    assert store.is_file()


def test_confirm_rejects_empty_goals(tmp_path, monkeypatch):
    monkeypatch.setattr(mp, "_STORE", tmp_path / "planner_morning_confirm.json")
    with pytest.raises(mp.GoalsRequiredError, match="Goals required"):
        mp.confirm_plan_today(1, goals="", skip_window_check=True)
    with pytest.raises(mp.GoalsRequiredError):
        mp.confirm_plan_today(1, goals="ab", skip_window_check=True)
    assert mp.is_plan_confirmed(1) is False
    out = mp.confirm_plan_today(1, goals="abc", skip_window_check=True)
    assert out["confirmed"] is True
    assert out["goals_ok"] is True
