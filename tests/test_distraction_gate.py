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


def test_should_hard_block_desktop_distraction_categories():
    """Armed mode kills Discord/Spotify/Netflix desktop — not whole browsers."""
    policy = {
        "hard_block_enabled": True,
        "hard_block_gaming": True,
        "hard_block_exes": [],
    }
    assert should_hard_block("discord.exe", "Social Media", policy)
    assert should_hard_block("spotify.exe", "Music / Media", policy)
    assert should_hard_block("netflix.exe", "Video Streaming", policy)
    assert should_hard_block("twitch.exe", "Live Streaming", policy)
    assert should_hard_block("someplayer.exe", "Entertainment", policy)
    # Seed list covers Discord even if category is wrong/Other
    assert should_hard_block("discord.exe", "Other", policy)
    assert should_hard_block("spotify.exe", "Other", policy)
    # Browsers stay extension-only
    assert not should_hard_block("chrome.exe", "Video Streaming", policy)
    assert not should_hard_block("msedge.exe", "Music / Media", policy)
    assert not should_hard_block("slack.exe", "Communication", policy)


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
        "hard_block_exes": ["explorer.exe", "python.exe", "Cursor.exe", "chrome.exe", "msedge.exe"],
    }
    assert not should_hard_block("explorer.exe", "Gaming", policy)
    assert not should_hard_block("python.exe", "Gaming", policy)
    assert not should_hard_block("Cursor.exe", "IDE / Code Editor", policy)
    assert not should_hard_block("chrome.exe", "Other (Browser)", policy)
    assert not should_hard_block("msedge.exe", "Other (Browser)", policy)
    assert not should_hard_block("zen.exe", "Other (Browser)", policy)


def test_commitment_escape_tools_blocked_when_armed():
    """Task Manager etc. are closed while hard-block is armed so tracker is harder to kill."""
    policy = {
        "hard_block_enabled": True,
        "hard_block_gaming": True,
        "hard_block_exes": [],
    }
    assert should_hard_block("taskmgr.exe", "Other", policy)
    assert should_hard_block("procexp64.exe", "Other", policy)
    assert not should_hard_block(
        "taskmgr.exe",
        "Other",
        {**policy, "hard_block_enabled": False},
    )


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


def test_seed_exes_apply_even_if_custom_list_empty():
    """Empty hard_block_exes must not disable Steam when hard_block_gaming is on."""
    from backend.behavior.distraction_gate import hard_block_exe_set

    policy = {
        "hard_block_enabled": True,
        "hard_block_gaming": True,
        "hard_block_exes": [],
    }
    assert "steam.exe" in hard_block_exe_set(policy)
    assert should_hard_block("steam.exe", "Other", policy)
    assert should_hard_block("steamwebhelper.exe", "Other", policy)
    # Browsers / Cursor stay protected even if somehow listed
    assert not should_hard_block("chrome.exe", "Other", policy)
    assert not should_hard_block("Cursor.exe", "IDE / Code Editor", policy)


def test_disarmed_never_blocks_games():
    policy = {
        "hard_block_enabled": False,
        "hard_block_gaming": True,
        "hard_block_exes": list(DEFAULT_HARD_BLOCK_EXES),
    }
    assert not should_hard_block("steam.exe", "Gaming", policy)
    assert not should_hard_block("MHUR.exe", "Gaming", policy)
    assert not should_hard_block("start_protected_game.exe", "Other", policy)


def test_compute_gate_unlocks_when_goal_met(monkeypatch, tmp_path):
    from backend.behavior import distraction_gate as dg
    from backend.planner import morning_rewards as mr

    monkeypatch.setattr(mr, "_STORE", tmp_path / "morning_rewards.json")
    monkeypatch.setattr("backend.bible.store.chapter_goal_met", lambda uid: True)

    class FakeSess:
        def __init__(self, mins: int, score: int):
            from datetime import datetime, timedelta, timezone

            # Must fall inside today's local day bounds (productive minutes clip to day).
            self.start_time = datetime.now(timezone.utc).replace(
                hour=8, minute=0, second=0, microsecond=0
            )
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
    monkeypatch.setattr(
        "backend.bible.store.summary",
        lambda uid: {
            "bible_minutes": 0,
            "game_bank_remaining_seconds": 0,
            "game_bank_remaining_minutes": 0,
            "day_pass": False,
            "chapter_goal": {"met": True, "target": 1, "completed": 1},
            "chapters_completed_today": ["John 1"],
            "day_pass_status": {"used": 0, "limit": 2, "remaining": 2},
        },
    )
    monkeypatch.setattr(
        "backend.planner.morning_plan.count_blocks_today",
        lambda db, uid, day=None: 2,
    )
    monkeypatch.setattr(
        "backend.planner.morning_plan.is_plan_confirmed",
        lambda uid, day=None: True,
    )

    out = mod.compute_distraction_gate(FakeDb(), 1)
    assert out["enabled"] is True
    assert out["productive_minutes"] == 120
    assert out["productive_label"] == "2 hours"
    assert out["daily_goal_label"]
    assert out["unlocked"] is True
    assert out["locked"] is False
    assert out["remaining_minutes"] == 0
    assert out["chapter_goal_met"] is True
    assert out["morning"]["next"] == "open"
    assert out["morning"]["bible_done"] is True
    assert out["morning"]["plan_done"] is True


def test_morning_gate_bible_then_plan(monkeypatch, tmp_path):
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

    monkeypatch.setattr(
        "backend.bible.store.summary",
        lambda uid: {
            "bible_minutes": 0,
            "game_bank_remaining_seconds": 0,
            "game_bank_remaining_minutes": 0,
            "day_pass": False,
            "chapter_goal": {"met": False, "target": 1, "completed": 0},
            "chapters_completed_today": [],
            "day_pass_status": {},
        },
    )
    monkeypatch.setattr("backend.bible.store.chapter_goal_met", lambda uid: False)
    monkeypatch.setattr(
        "backend.planner.morning_plan.count_blocks_today",
        lambda db, uid, day=None: 0,
    )
    monkeypatch.setattr(
        "backend.planner.morning_plan.is_plan_confirmed",
        lambda uid, day=None: False,
    )
    out = mod.compute_distraction_gate(FakeDb(), 1)
    assert out["morning"]["next"] == "bible"
    assert out["morning"]["allow_paths"] == ["/bible", "/login"]

    monkeypatch.setattr(
        "backend.bible.store.summary",
        lambda uid: {
            "bible_minutes": 5,
            "game_bank_remaining_seconds": 0,
            "game_bank_remaining_minutes": 0,
            "day_pass": False,
            "chapter_goal": {"met": True, "target": 1, "completed": 1},
            "chapters_completed_today": ["John 1"],
            "day_pass_status": {},
        },
    )
    monkeypatch.setattr("backend.bible.store.chapter_goal_met", lambda uid: True)
    out2 = mod.compute_distraction_gate(FakeDb(), 1)
    assert out2["morning"]["next"] == "plan"
    assert "/productivity" in out2["morning"]["allow_paths"]
    assert out2["morning"]["rewards"]["awards"]["bible"]["granted"] is True

    monkeypatch.setattr(
        "backend.planner.morning_plan.is_plan_confirmed",
        lambda uid, day=None: True,
    )
    out3 = mod.compute_distraction_gate(FakeDb(), 1)
    assert out3["morning"]["next"] == "open"
    assert "rewards" in out3["morning"]


def test_earned_reward_day_bypasses_morning_browser_gate(monkeypatch, tmp_path):
    from backend.behavior import distraction_gate as mod
    from backend.behavior import reward_days

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
            "hard_block_enabled": True,
            "daily_goal_minutes": 240,
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
    monkeypatch.setattr(
        "backend.bible.store.summary",
        lambda uid: {
            "bible_minutes": 0,
            "game_bank_remaining_seconds": 0,
            "game_bank_remaining_minutes": 0,
            "day_pass": False,
            "reward_day": True,
            "chapter_goal": {"met": False, "target": 1, "completed": 0},
            "chapters_completed_today": [],
            "day_pass_status": {},
        },
    )
    monkeypatch.setattr(reward_days, "record_qualifying_day", lambda uid, qualified: {"available": 0})
    monkeypatch.setattr("backend.planner.morning_plan.count_blocks_today", lambda db, uid, day=None: 0)
    monkeypatch.setattr(
        "backend.planner.morning_plan.is_plan_confirmed", lambda uid, day=None: False
    )
    monkeypatch.setenv("MORNING_GATE", "1")

    out = mod.compute_distraction_gate(FakeDb(), 1)
    assert out["reward_day"] is True
    assert out["day_unlimited"] is True
    assert out["morning"]["next"] == "open"
    assert out["browser"]["mode"] == "free"


def test_gate_refresh_is_read_only_no_auto_draft_or_lazy_confirm(monkeypatch, tmp_path):
    """Gate consumers (SPA poll / tracker) must not allocate or confirm plans."""
    from backend.behavior import distraction_gate as mod
    from backend.planner import morning_rewards as mr

    monkeypatch.setattr(mr, "_STORE", tmp_path / "morning_rewards.json")
    draft_calls: list[dict] = []
    confirm_calls: list[dict] = []

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
    monkeypatch.setenv("MORNING_AUTO_PLAN", "1")
    monkeypatch.setattr(
        "backend.bible.store.summary",
        lambda uid: {
            "bible_minutes": 5,
            "game_bank_remaining_seconds": 0,
            "game_bank_remaining_minutes": 0,
            "day_pass": False,
            "reward_day": False,
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

    def _fake_draft(*a, **k):
        draft_calls.append(dict(k))
        return {
            "ok": True,
            "skipped": False,
            "created": 3,
            "auto_plan": {"drafted": True, "created": 3, "titles": ["X"]},
        }

    def _fake_confirm(*a, **k):
        confirm_calls.append(dict(k))
        return {"confirmed": True}

    monkeypatch.setattr("backend.planner.auto_plan.auto_draft_day_plan", _fake_draft)
    monkeypatch.setattr("backend.planner.morning_plan.confirm_plan_today", _fake_confirm)

    out = mod.compute_distraction_gate(FakeDb(), 1)
    assert out["morning"]["next"] == "plan"
    assert out["morning"]["plan_done"] is False
    assert draft_calls == []
    assert confirm_calls == []

    # Existing calendar blocks also must not silently confirm the morning plan.
    monkeypatch.setattr(
        "backend.planner.morning_plan.count_blocks_today",
        lambda db, uid, day=None: 4,
    )
    out2 = mod.compute_distraction_gate(FakeDb(), 1)
    assert out2["morning"]["next"] == "plan"
    assert out2["morning"]["plan_done"] is False
    assert confirm_calls == []
    assert draft_calls == []
