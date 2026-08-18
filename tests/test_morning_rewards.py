"""Unit tests for morning rewards + gate transitions."""

from __future__ import annotations

import pytest

from backend.planner import morning_plan as mp
from backend.planner import morning_rewards as mr


@pytest.fixture(autouse=True)
def _silence_bible_tts(monkeypatch):
    monkeypatch.setattr(
        "backend.behavior.voice_agent.dialogues.speak",
        lambda *a, **k: "",
    )


def test_bible_and_plan_rewards_idempotent(tmp_path, monkeypatch):
    store = tmp_path / "morning_rewards.json"
    monkeypatch.setattr(mr, "_STORE", store)

    s1 = mr.grant(1, "bible")
    assert s1["awards"]["bible"]["granted"] is True
    assert s1["total_points"] == 10
    s1b = mr.grant(1, "bible")
    assert s1b["total_points"] == 10  # idempotent

    s2 = mr.grant_plan(1)
    assert s2["awards"]["plan"]["granted"] is True
    assert s2["total_points"] == 20
    s2b = mr.grant_plan(1)
    assert s2b["total_points"] == 20


def test_confirm_plan_grants_plan_reward(tmp_path, monkeypatch):
    confirm_store = tmp_path / "planner_morning_confirm.json"
    reward_store = tmp_path / "morning_rewards.json"
    monkeypatch.setattr(mp, "_STORE", confirm_store)
    monkeypatch.setattr(mr, "_STORE", reward_store)

    out = mp.confirm_plan_today(7, skip_window_check=True, goals="Hit focus target")
    assert out["confirmed"] is True
    assert out["morning_rewards"]["awards"]["plan"]["granted"] is True
    assert mr.summary(7)["total_points"] == 10


def test_maybe_grant_bible_when_goal_met(tmp_path, monkeypatch):
    reward_store = tmp_path / "morning_rewards.json"
    monkeypatch.setattr(mr, "_STORE", reward_store)
    monkeypatch.setattr(
        "backend.bible.store.chapter_goal_met",
        lambda uid: uid == 1,
    )
    out = mr.maybe_grant_bible(1)
    assert out["awards"]["bible"]["granted"] is True
    out2 = mr.maybe_grant_bible(2)
    assert out2["awards"]["bible"]["granted"] is False
    assert out2["total_points"] == 0


def test_morning_gate_exposes_rewards(monkeypatch, tmp_path):
    from backend.behavior import distraction_gate as mod

    class FakeQuery:
        def filter(self, *a, **k):
            return self

        def all(self):
            return []

    class FakeDb:
        def query(self, *a, **k):
            return FakeQuery()

    reward_store = tmp_path / "morning_rewards.json"
    monkeypatch.setattr(mr, "_STORE", reward_store)
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
        lambda db, uid, day=None: 1,
    )
    monkeypatch.setattr(
        "backend.planner.morning_plan.is_plan_confirmed",
        lambda uid, day=None: False,
    )

    out = mod.compute_distraction_gate(FakeDb(), 1)
    assert out["morning"]["next"] == "plan"
    assert out["morning"]["bible_done"] is True
    assert out["morning"]["rewards"]["awards"]["bible"]["granted"] is True
    assert out["morning"]["rewards"]["total_points"] == 10
    assert "hint" in out["morning"]


def test_tracker_toggle_syncs_day_chapters(tmp_path, monkeypatch):
    """Desktop tracker tick must count for morning bible_done (same day json)."""
    from backend.bible import store as bible_store

    monkeypatch.setattr(bible_store, "bible_dir", lambda: tmp_path)
    monkeypatch.setattr(bible_store, "_day_key", lambda: "2026-08-04")
    reward_store = tmp_path / "morning_rewards.json"
    monkeypatch.setattr(mr, "_STORE", reward_store)

    assert bible_store.chapter_goal_met(1) is False
    today = bible_store.resolve_today_chapter(1)
    out = bible_store.toggle_chapter_manual(1, today["key"])
    assert out["completed"] is True
    assert today["key"] in bible_store.chapters_completed_today(1)
    assert bible_store.chapter_goal_met(1) is True
    assert out.get("morning_rewards", {}).get("awards", {}).get("bible", {}).get("granted") is True

    # Non-assigned chapter is rejected
    bad = bible_store.toggle_chapter_manual(1, "John|1")
    assert bad["ok"] is False
