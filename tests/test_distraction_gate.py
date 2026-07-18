"""Tests for distraction hard-block gate."""

from backend.behavior.distraction_gate import (
    DEFAULT_HARD_BLOCK_EXES,
    should_hard_block,
)


def test_should_hard_block_exe_list():
    policy = {
        "hard_block_enabled": True,
        "hard_block_gaming": False,
        "hard_block_exes": ["Steam.exe", "MyGame.exe"],
    }
    assert should_hard_block("steam.exe", "Other", policy)
    assert should_hard_block("C:\\\\Games\\\\MyGame.exe", "Other", policy)
    assert not should_hard_block("code.exe", "IDE / Code Editor", policy)


def test_should_hard_block_gaming_category():
    policy = {
        "hard_block_enabled": True,
        "hard_block_gaming": True,
        "hard_block_exes": [],
    }
    assert should_hard_block("something.exe", "Gaming", policy)
    assert not should_hard_block("code.exe", "IDE / Code Editor", policy)


def test_disabled_never_blocks():
    policy = {
        "hard_block_enabled": False,
        "hard_block_gaming": True,
        "hard_block_exes": list(DEFAULT_HARD_BLOCK_EXES),
    }
    assert not should_hard_block("steam.exe", "Gaming", policy)


def test_protected_exe_never_blocked():
    policy = {
        "hard_block_enabled": True,
        "hard_block_gaming": True,
        "hard_block_exes": ["explorer.exe", "python.exe"],
    }
    assert not should_hard_block("explorer.exe", "Gaming", policy)
    assert not should_hard_block("python.exe", "Gaming", policy)


def test_start_protected_game_blocked_by_name():
    from backend.behavior.distraction_gate import looks_like_game_process

    policy = {
        "hard_block_enabled": True,
        "hard_block_gaming": True,
        "hard_block_exes": [],
    }
    assert looks_like_game_process("start_protected_game.exe", 0)
    assert should_hard_block("start_protected_game.exe", "Other", policy, pid=0)
    assert should_hard_block("steamwebhelper.exe", "Other", policy, pid=0)


def test_compute_gate_unlocks_when_goal_met(monkeypatch):
    from backend.behavior import distraction_gate as dg

    class FakeSess:
        def __init__(self, mins: int, score: int):
            from datetime import datetime, timedelta, timezone

            self.start_time = datetime(2026, 7, 17, 8, 0, tzinfo=timezone.utc)
            self.end_time = self.start_time + timedelta(minutes=mins)
            self._score = score
            self.category = "IDE / Code Editor"
            self.app_name = "code.exe"
            self.window_title = "x"
            self.override_productive = None

    class FakeQuery:
        def __init__(self, rows):
            self._rows = rows

        def filter(self, *a, **k):
            return self

        def all(self):
            return self._rows

    class FakeDb:
        def query(self, *a, **k):
            return FakeQuery([FakeSess(120, 90), FakeSess(30, 10)])

    monkeypatch.setattr(
        dg,
        "compute_distraction_gate",
        dg.compute_distraction_gate,
    )

    # Patch dependencies used inside compute
    import backend.behavior.distraction_gate as mod

    monkeypatch.setattr(
        "backend.behavior.productivity_policy.load_policy_dict",
        lambda db, uid: {
            "hard_block_enabled": True,
            "daily_goal_minutes": 100,
            "threshold": 60,
            "hard_block_gaming": True,
            "hard_block_exes": [],
            "productive_categories": [],
            "blocked_categories": [],
            "app_overrides": {},
        },
    )
    monkeypatch.setattr(
        "backend.behavior.category_scores.load_score_map",
        lambda db: {},
    )
    monkeypatch.setattr(
        "backend.behavior.productivity_policy.resolve_session_score",
        lambda sess, scores, policy: sess._score,
    )

    out = mod.compute_distraction_gate(FakeDb(), 1)
    assert out["enabled"] is True
    assert out["productive_minutes"] == 120
    assert out["unlocked"] is True
    assert out["locked"] is False
    assert out["remaining_minutes"] == 0
