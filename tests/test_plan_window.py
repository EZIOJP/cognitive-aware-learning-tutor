"""Plan confirm window — before / during / after EOD."""

from __future__ import annotations

from datetime import datetime

import pytest

from backend.planner import morning_plan as mp
from backend.planner.service import local_tz


def _dt(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=local_tz())


def test_parse_hhmm_defaults(monkeypatch):
    monkeypatch.delenv("MORNING_PLAN_START", raising=False)
    monkeypatch.delenv("MORNING_PLAN_EOD", raising=False)
    assert mp.parse_hhmm(None, default="05:00") == (5, 0)
    assert mp.plan_start_hhmm() == "05:00"
    assert mp.plan_eod_hhmm() == "23:59"


def test_parse_hhmm_env(monkeypatch):
    monkeypatch.setenv("MORNING_PLAN_START", "6:30")
    monkeypatch.setenv("MORNING_PLAN_EOD", "22:00")
    assert mp.plan_start_hhmm() == "06:30"
    assert mp.plan_eod_hhmm() == "22:00"


def test_window_start_max_of_bible_and_clock(monkeypatch):
    monkeypatch.setenv("MORNING_PLAN_START", "05:00")
    monkeypatch.setenv("MORNING_PLAN_EOD", "23:59")
    day = _dt(2026, 8, 4, 12).date()

    # Bible at 03:00 → window opens at 05:00
    start, end = mp.plan_window_bounds(day, bible_completed_at=_dt(2026, 8, 4, 3, 0))
    assert start == _dt(2026, 8, 4, 5, 0)
    assert end.hour == 23 and end.minute == 59

    # Bible at 10:15 → window opens at 10:15
    start2, _ = mp.plan_window_bounds(day, bible_completed_at=_dt(2026, 8, 4, 10, 15))
    assert start2 == _dt(2026, 8, 4, 10, 15)


def test_before_window_confirm_soft_open(monkeypatch):
    """Before MORNING_PLAN_START — confirm still allowed (soft planning)."""
    monkeypatch.setenv("MORNING_PLAN_START", "05:00")
    monkeypatch.setenv("MORNING_PLAN_EOD", "23:59")
    now = _dt(2026, 8, 4, 4, 30)
    w = mp.evaluate_plan_window(
        bible_done=True,
        bible_completed_at=_dt(2026, 8, 4, 3, 0),
        now=now,
    )
    assert w["phase"] == "before_start"
    assert w["confirm_available"] is True
    assert w.get("soft") is True
    assert "anytime" in w["reason"].lower() or "typical" in w["reason"].lower()


def test_during_window_confirm_allowed(monkeypatch):
    monkeypatch.setenv("MORNING_PLAN_START", "05:00")
    monkeypatch.setenv("MORNING_PLAN_EOD", "23:59")
    now = _dt(2026, 8, 4, 9, 0)
    w = mp.evaluate_plan_window(
        bible_done=True,
        bible_completed_at=_dt(2026, 8, 4, 6, 0),
        now=now,
    )
    assert w["phase"] == "open"
    assert w["confirm_available"] is True
    assert "until" in w["reason"].lower() or "ready" in w["reason"].lower()


def test_after_eod_confirm_still_soft(monkeypatch):
    monkeypatch.setenv("MORNING_PLAN_START", "05:00")
    monkeypatch.setenv("MORNING_PLAN_EOD", "22:00")
    w = mp.evaluate_plan_window(
        bible_done=True,
        bible_completed_at=_dt(2026, 8, 4, 8, 0),
        now=_dt(2026, 8, 4, 22, 30),
    )
    assert w["phase"] == "after_eod"
    assert w["confirm_available"] is True
    assert w["eod_hhmm"] == "22:00"


def test_assert_allows_after_eod_when_soft(monkeypatch):
    monkeypatch.setenv("MORNING_PLAN_START", "05:00")
    monkeypatch.setenv("MORNING_PLAN_EOD", "22:00")
    w = mp.assert_plan_confirm_allowed(
        bible_done=True,
        bible_completed_at=_dt(2026, 8, 4, 8, 0),
        now=_dt(2026, 8, 4, 22, 30),
    )
    assert w["confirm_available"] is True


def test_assert_rejects_without_bible(monkeypatch):
    monkeypatch.setenv("MORNING_PLAN_START", "05:00")
    monkeypatch.setenv("MORNING_PLAN_EOD", "22:00")
    with pytest.raises(mp.PlanWindowError):
        mp.assert_plan_confirm_allowed(
            bible_done=False,
            now=_dt(2026, 8, 4, 9, 0),
        )


def test_confirm_ok_before_usual_start(tmp_path, monkeypatch):
    """Soft planning: confirm works before MORNING_PLAN_START."""
    from backend.planner import morning_rewards as mr

    monkeypatch.setattr(mp, "_STORE", tmp_path / "planner_morning_confirm.json")
    monkeypatch.setattr(mr, "_STORE", tmp_path / "morning_rewards.json")
    monkeypatch.setenv("MORNING_PLAN_START", "05:00")
    monkeypatch.setenv("MORNING_PLAN_EOD", "23:59")
    out = mp.confirm_plan_today(
        1,
        bible_done=True,
        bible_completed_at=_dt(2026, 8, 4, 3, 0),
        now=_dt(2026, 8, 4, 4, 0),
        goals="Study Scaler today",
    )
    assert out["confirmed"] is True
    assert mp.is_plan_confirmed(1, _dt(2026, 8, 4, 4).date())


def test_confirm_ok_during_window(tmp_path, monkeypatch):
    from backend.planner import morning_rewards as mr

    monkeypatch.setattr(mp, "_STORE", tmp_path / "planner_morning_confirm.json")
    monkeypatch.setattr(mr, "_STORE", tmp_path / "morning_rewards.json")
    monkeypatch.setenv("MORNING_PLAN_START", "05:00")
    monkeypatch.setenv("MORNING_PLAN_EOD", "23:59")
    out = mp.confirm_plan_today(
        1,
        bible_done=True,
        bible_completed_at=_dt(2026, 8, 4, 6, 0),
        now=_dt(2026, 8, 4, 10, 0),
        goals="Complete Scaler lesson and practice",
    )
    assert out["confirmed"] is True
    assert mp.is_plan_confirmed(1, _dt(2026, 8, 4, 10).date())


def test_gate_after_eod_opens_without_plan(monkeypatch, tmp_path):
    from backend.behavior import distraction_gate as mod
    from backend.planner import morning_rewards as mr

    monkeypatch.setattr(mr, "_STORE", tmp_path / "morning_rewards.json")

    class FakeQuery:
        def filter(self, *a, **k):
            return self

        def all(self):
            return []

    class FakeDb:
        def query(self, *a, **k):
            return FakeQuery()

    monkeypatch.setattr(
        "backend.behavior.productivity_policy.load_policy_dict",
        lambda db, uid: {
            "hard_block_enabled": False,
            "daily_goal_minutes": 100,
            "threshold": 60,
            "hard_block_gaming": True,
            "hard_block_exes": [],
            "productive_categories": [],
            "blocked_categories": [],
            "app_overrides": {},
        },
    )
    monkeypatch.setattr("backend.behavior.category_scores.load_score_map", lambda db: {})
    monkeypatch.setattr(
        "backend.behavior.productivity_policy.resolve_session_score",
        lambda sess, scores, policy: 0,
    )
    monkeypatch.setenv("MORNING_GATE", "1")
    monkeypatch.setenv("MORNING_PLAN_START", "05:00")
    monkeypatch.setenv("MORNING_PLAN_EOD", "22:00")
    monkeypatch.setattr(
        "backend.bible.store.summary",
        lambda uid: {
            "bible_minutes": 5,
            "game_bank_remaining_seconds": 0,
            "game_bank_remaining_minutes": 0,
            "day_pass": False,
            "chapter_goal": {"met": True, "target": 1, "completed": 1},
            "chapters_completed_today": ["John|1"],
            "day_pass_status": {},
        },
    )
    monkeypatch.setattr("backend.bible.store.chapter_goal_met", lambda uid: True)
    monkeypatch.setattr(
        "backend.planner.morning_plan.count_blocks_today",
        lambda db, uid, day=None: 0,
    )
    monkeypatch.setattr(
        "backend.planner.morning_plan.is_plan_confirmed",
        lambda uid, day=None: False,
    )

    # Freeze "now" past EOD via evaluate_plan_window
    real_eval = mp.evaluate_plan_window

    def _eval_past(**kwargs):
        kwargs = dict(kwargs)
        kwargs["now"] = _dt(2026, 8, 4, 22, 30)
        kwargs.setdefault("bible_completed_at", _dt(2026, 8, 4, 8, 0).isoformat())
        return real_eval(**kwargs)

    monkeypatch.setattr("backend.planner.morning_plan.evaluate_plan_window", _eval_past)

    out = mod.compute_distraction_gate(FakeDb(), 1)
    assert out["morning"]["next"] == "open"
    assert out["morning"]["plan_done"] is False
    assert out["morning"]["plan_window"]["phase"] == "after_eod"
    hint = (out["morning"]["hint"] or "").lower()
    assert "usual end" in hint or "soft-land" in hint or "confirm" in hint


def test_gate_before_start_stays_on_plan(monkeypatch, tmp_path):
    from backend.behavior import distraction_gate as mod
    from backend.planner import morning_rewards as mr

    monkeypatch.setattr(mr, "_STORE", tmp_path / "morning_rewards.json")

    class FakeQuery:
        def filter(self, *a, **k):
            return self

        def all(self):
            return []

    class FakeDb:
        def query(self, *a, **k):
            return FakeQuery()

    monkeypatch.setattr(
        "backend.behavior.productivity_policy.load_policy_dict",
        lambda db, uid: {
            "hard_block_enabled": False,
            "daily_goal_minutes": 100,
            "threshold": 60,
            "hard_block_gaming": True,
            "hard_block_exes": [],
            "productive_categories": [],
            "blocked_categories": [],
            "app_overrides": {},
        },
    )
    monkeypatch.setattr("backend.behavior.category_scores.load_score_map", lambda db: {})
    monkeypatch.setattr(
        "backend.behavior.productivity_policy.resolve_session_score",
        lambda sess, scores, policy: 0,
    )
    monkeypatch.setenv("MORNING_GATE", "1")
    monkeypatch.setenv("MORNING_PLAN_START", "05:00")
    monkeypatch.setenv("MORNING_PLAN_EOD", "23:59")
    monkeypatch.setattr(
        "backend.bible.store.summary",
        lambda uid: {
            "bible_minutes": 5,
            "game_bank_remaining_seconds": 0,
            "game_bank_remaining_minutes": 0,
            "day_pass": False,
            "chapter_goal": {"met": True, "target": 1, "completed": 1},
            "chapters_completed_today": ["John|1"],
            "day_pass_status": {},
        },
    )
    monkeypatch.setattr("backend.bible.store.chapter_goal_met", lambda uid: True)
    monkeypatch.setattr(
        "backend.planner.morning_plan.count_blocks_today",
        lambda db, uid, day=None: 0,
    )
    monkeypatch.setattr(
        "backend.planner.morning_plan.is_plan_confirmed",
        lambda uid, day=None: False,
    )

    real_eval = mp.evaluate_plan_window

    def _eval_early(**kwargs):
        kwargs = dict(kwargs)
        kwargs["now"] = _dt(2026, 8, 4, 4, 0)
        kwargs.setdefault("bible_completed_at", _dt(2026, 8, 4, 3, 0).isoformat())
        return real_eval(**kwargs)

    monkeypatch.setattr("backend.planner.morning_plan.evaluate_plan_window", _eval_early)

    out = mod.compute_distraction_gate(FakeDb(), 1)
    assert out["morning"]["next"] == "plan"
    assert out["morning"]["plan_window"]["confirm_available"] is True
    assert out["morning"]["plan_window"]["phase"] == "before_start"
    hint = (out["morning"]["hint"] or "").lower()
    assert "anytime" in hint or "typical" in hint
