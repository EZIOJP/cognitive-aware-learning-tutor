"""Edge-case tests for server lifecycle kill filters (no real process kills)."""
from __future__ import annotations

import os
from unittest.mock import patch

from scripts.server_lifecycle import (
    filter_killable_pids,
    is_calt_api_cmdline,
    is_calt_frontend_cmdline,
    is_protected_cmdline,
)


ROOT = r"C:\Users\Lenovo\Desktop\Cognitive-Aware Learning Tutor"


def test_tracker_cmdline_is_protected():
    cmd = rf'"{ROOT}\.venv\Scripts\pythonw.exe" -m backend.behavior.desktop_tracker'
    assert is_protected_cmdline(cmd)
    assert not is_calt_api_cmdline(cmd)
    assert not is_calt_frontend_cmdline(cmd)


def test_uvicorn_is_api_not_protected():
    cmd = rf'"{ROOT}\.venv\Scripts\python.exe" -m uvicorn backend.main:app --host 0.0.0.0 --port 8000'
    assert not is_protected_cmdline(cmd)
    assert is_calt_api_cmdline(cmd)


def test_vite_is_frontend():
    cmd = rf'node "{ROOT}\node_modules\vite\bin\vite.js"'
    assert is_calt_frontend_cmdline(cmd)
    assert not is_protected_cmdline(cmd)


def test_random_python_not_killed_as_api():
    cmd = r"C:\Python314\python.exe myscript.py"
    assert not is_calt_api_cmdline(cmd)
    assert not is_calt_frontend_cmdline(cmd)


def test_filter_skips_tracker_and_self():
    tracker_cmd = rf"{ROOT}\.venv\Scripts\pythonw.exe -m backend.behavior.desktop_tracker"
    api_cmd = rf"{ROOT}\.venv\Scripts\python.exe -m uvicorn backend.main:app --port 8000"

    def fake_cmdline(pid: int):
        return {111: tracker_cmd, 222: api_cmd, os.getpid(): "server_lifecycle.py menu"}.get(pid)

    with patch("scripts.server_lifecycle._cmdline_for_pid", side_effect=fake_cmdline):
        killable, skipped = filter_killable_pids([111, 222, os.getpid()], kind="api")
    assert 222 in killable
    assert 111 not in killable
    assert os.getpid() not in killable
    reasons = " ".join(r for _, r in skipped).lower()
    assert "protected" in reasons or "tracker" in reasons
    assert "self" in reasons


def test_foreign_port_holder_skipped():
    foreign = "C:\\SomeOtherApp\\server.exe --port 8000"

    with patch("scripts.server_lifecycle._cmdline_for_pid", return_value=foreign):
        killable, skipped = filter_killable_pids([999], kind="port-api")
    assert killable == []
    assert skipped and "foreign" in skipped[0][1].lower()


def test_close_plan_never_lists_tracker():
    from scripts.server_lifecycle import build_close_plan

    tracker_cmd = rf"{ROOT}\.venv\Scripts\pythonw.exe -m backend.behavior.desktop_tracker"
    api_cmd = rf"{ROOT}\.venv\Scripts\python.exe -m uvicorn backend.main:app --port 8000"

    def fake_cmdline(pid: int):
        return {10: tracker_cmd, 20: api_cmd}.get(pid)

    with (
        patch("scripts.server_lifecycle.tracker_pids", return_value=[10]),
        patch("scripts.server_lifecycle._listening_pids", side_effect=lambda port: [20] if port == 8000 else []),
        patch("scripts.server_lifecycle._http_ok", return_value=True),
        patch("scripts.server_lifecycle._orphan_calt_pids", return_value={"api": [20], "frontend": []}),
        patch("scripts.server_lifecycle._cmdline_for_pid", side_effect=fake_cmdline),
    ):
        plan = build_close_plan("api")
    assert 10 not in plan.kill_all
    assert 20 in plan.kill_api
    assert plan.api_was_healthy
    assert any("HEALTHY" in w for w in plan.warnings)
    assert any("PROTECTED" in w or "tracker" in w.lower() for w in plan.warnings)
