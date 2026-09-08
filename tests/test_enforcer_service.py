"""Unit tests for the thin Windows enforcer loop (v2b). Offline — no real kills."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from backend.behavior.enforcer_service.service import (
    enforce_once,
    resolve_enforcer_user_id,
)


def test_resolve_enforcer_user_id_reuses_tracker_path():
    """Same resolution as desktop tracker: TrackerConfig + resolve_user_id."""
    cfg = MagicMock()
    cfg.user_id = None
    with (
        patch(
            "backend.behavior.enforcer_service.service.TrackerConfig.load",
            return_value=cfg,
        ),
        patch(
            "backend.behavior.enforcer_service.service.resolve_user_id",
            return_value=42,
        ) as resolve,
    ):
        assert resolve_enforcer_user_id() == 42
        resolve.assert_called_once_with(cfg)


def test_enforce_once_kills_when_gate_locked_and_hard_block_armed():
    gate = {"locked": True, "enabled": True}
    policy = {"hard_block_enabled": True, "hard_block_exes": ["steam.exe"]}
    kills: list[tuple[int, str]] = []

    def _terminate(pid: int, *, exe: str = "") -> bool:
        kills.append((pid, exe))
        return True

    n = enforce_once(
        user_id=1,
        db=MagicMock(),
        compute_gate=lambda _db, _uid: gate,
        load_policy=lambda _db, _uid: policy,
        list_blockable=lambda _pol: [(4242, "steam.exe"), (4243, "discord.exe")],
        terminate=_terminate,
    )
    assert n == 2
    assert kills == [(4242, "steam.exe"), (4243, "discord.exe")]


def test_enforce_once_skips_when_hard_block_disarmed():
    gate = {"locked": True, "enabled": False}
    policy = {"hard_block_enabled": False}
    terminate = MagicMock(return_value=True)
    list_blockable = MagicMock(return_value=[(99, "steam.exe")])

    n = enforce_once(
        user_id=1,
        db=MagicMock(),
        compute_gate=lambda _db, _uid: gate,
        load_policy=lambda _db, _uid: policy,
        list_blockable=list_blockable,
        terminate=terminate,
    )
    assert n == 0
    list_blockable.assert_not_called()
    terminate.assert_not_called()


def test_enforce_once_skips_when_gate_unlocked():
    """Armed but unlocked (goal met / free override) — do not kill (unless incubating)."""
    gate = {"locked": False, "enabled": True}
    policy = {"hard_block_enabled": True}
    terminate = MagicMock(return_value=True)
    list_blockable = MagicMock(return_value=[(99, "steam.exe")])

    with (
        patch("backend.behavior.break_reward.tick_incubation", return_value={"active": False}),
        patch("backend.behavior.break_reward.force_study_hard", return_value=False),
    ):
        n = enforce_once(
            user_id=1,
            db=MagicMock(),
            compute_gate=lambda _db, _uid: gate,
            load_policy=lambda _db, _uid: policy,
            list_blockable=list_blockable,
            terminate=terminate,
        )
    assert n == 0
    list_blockable.assert_not_called()
    terminate.assert_not_called()


def test_enforce_once_kills_when_incubating_even_if_unlocked():
    """Q3 C2 — incubation forces study-hard kills while hard-block is armed."""
    gate = {"locked": False, "enabled": True}
    policy = {"hard_block_enabled": True}
    kills: list[tuple[int, str]] = []

    def _terminate(pid: int, *, exe: str = "") -> bool:
        kills.append((pid, exe))
        return True

    with (
        patch("backend.behavior.break_reward.tick_incubation", return_value={"active": True}),
        patch("backend.behavior.break_reward.force_study_hard", return_value=True),
    ):
        n = enforce_once(
            user_id=1,
            db=MagicMock(),
            compute_gate=lambda _db, _uid: gate,
            load_policy=lambda _db, _uid: policy,
            list_blockable=lambda _pol: [(11, "steam.exe")],
            terminate=_terminate,
        )
    assert n == 1
    assert kills == [(11, "steam.exe")]


def test_run_loop_stops_on_event():
    from backend.behavior.enforcer_service.service import run_loop
    import threading

    calls = {"n": 0}
    stop = threading.Event()

    def _once(**_kwargs):
        calls["n"] += 1
        if calls["n"] >= 2:
            stop.set()
        return 0

    with patch(
        "backend.behavior.enforcer_service.service.enforce_once",
        side_effect=_once,
    ):
        run_loop(user_id=1, poll_s=0.01, stop_event=stop, max_iterations=10)

    assert calls["n"] >= 2
