"""Tracker restart — unified bat + tray path."""

from __future__ import annotations

from backend.behavior import tracker_restart as tr


def test_wait_until_clear_when_empty(monkeypatch):
    monkeypatch.setattr(tr, "root_tracker_count", lambda **_: 0)
    monkeypatch.setattr(tr, "mutex_held", lambda: False)
    assert tr.wait_until_clear(timeout_s=1.0) is True


def test_run_restart_kills_then_launches(monkeypatch):
    killed: list[int] = []
    monkeypatch.setattr(tr, "kill_all_trackers", lambda: killed.append(1) or 2)
    monkeypatch.setattr(tr, "wait_until_clear", lambda **_: True)
    monkeypatch.setattr(tr.time, "sleep", lambda *_: None)
    monkeypatch.setattr(tr, "launch_tray_tracker", lambda **_: True)
    assert tr.run_restart(timeout_s=0.5) == 0
    assert killed


def test_show_confirm_dialog_yes(monkeypatch):
    monkeypatch.delenv("TRACKER_EXIT_PIN", raising=False)
    monkeypatch.setattr(tr.sys, "platform", "win32")
    monkeypatch.setattr(
        "ctypes.windll.user32.MessageBoxW",
        lambda *_a, **_k: 6,
        raising=False,
    )
    assert tr.show_confirm_dialog() is True


def test_confirm_subprocess(monkeypatch):
    monkeypatch.setattr(tr.subprocess, "call", lambda *_a, **_k: 0)
    assert tr.confirm_restart_subprocess() is True


def test_request_tray_restart_cancelled(monkeypatch):
    monkeypatch.setattr(tr, "confirm_restart_subprocess", lambda: False)
    spawned: list[bool] = []
    monkeypatch.setattr(tr, "spawn_restart_detached", lambda: spawned.append(True) or True)
    tr.request_tray_restart(None)
    assert not spawned


def test_request_tray_restart_flushes_and_spawns(monkeypatch):
    flushed: list[str] = []
    spawned: list[bool] = []

    class _Svc:
        def flush_current(self, reason: str):
            flushed.append(reason)

    monkeypatch.setattr(tr, "confirm_restart_subprocess", lambda: True)
    monkeypatch.setattr(tr, "spawn_restart_detached", lambda: spawned.append(True) or True)
    monkeypatch.setattr(
        "backend.behavior.tracker_storage.flush_pending_events",
        lambda: flushed.append("pending"),
    )
    tr.request_tray_restart(_Svc())
    assert flushed == ["restart", "pending"]
    assert spawned
