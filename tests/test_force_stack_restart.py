"""Force stack restart CLI / spawn helpers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from backend.behavior import force_stack_restart as fsr


def test_main_cli_stack_calls_restart_servers():
    with patch.object(fsr, "force_restart_servers", return_value=0) as mock_run:
        assert fsr.main_cli(["stack"]) == 0
        mock_run.assert_called_once_with(mode="stack", rebuild=False)


def test_main_cli_full_rebuilds_and_restarts_tracker():
    with (
        patch.object(fsr, "force_restart_servers", return_value=0) as mock_run,
        patch("backend.behavior.tracker_restart.run_restart", return_value=0) as mock_tr,
    ):
        assert fsr.main_cli(["full"]) == 0
        mock_run.assert_called_once_with(mode="full", rebuild=True)
        mock_tr.assert_called_once()


def test_main_cli_full_no_rebuild():
    with (
        patch.object(fsr, "force_restart_servers", return_value=0) as mock_run,
        patch("backend.behavior.tracker_restart.run_restart", return_value=0),
    ):
        assert fsr.main_cli(["full", "--no-rebuild"]) == 0
        mock_run.assert_called_once_with(mode="full", rebuild=False)


def test_spawn_force_restart_opens_console(monkeypatch):
    calls: list = []

    def fake_popen(cmd, **kw):
        calls.append(cmd)
        return MagicMock()

    monkeypatch.setattr(fsr.sys, "platform", "win32")
    monkeypatch.setattr(fsr.subprocess, "Popen", fake_popen)
    assert fsr.spawn_force_restart(mode="stack") is True
    assert calls
    assert calls[0][0] == "cmd"
    assert "force_stack_restart" in " ".join(str(x) for x in calls[0])
