"""Launch project scripts from the desktop tracker tray menu."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

from backend.paths import ROOT

log = logging.getLogger("desktop_tracker")

RUN_APP_BAT = ROOT / "run.bat"
STUDIO_BAT = ROOT / "transcript-notes-studio" / "run.bat"
LOGIN_URL = "http://localhost:5173/login"


def _start_console(title: str, work_dir: Path, inner: str) -> None:
    """Open a new cmd window and run *inner* after cd to *work_dir*."""
    if sys.platform != "win32":
        log.warning("Tray launchers are Windows-only")
        return
    cmd = f'cd /d "{work_dir}" & {inner}'
    try:
        subprocess.Popen(
            ["cmd", "/c", "start", title, "cmd", "/k", cmd],
            cwd=str(work_dir),
        )
        log.info("Launched %s", title)
    except OSError as exc:
        log.warning("Could not launch %s: %s", title, exc)


def launch_app_fe_be() -> None:
    """Start FastAPI + Vite via run.bat (same as project root run.bat).

    Does **not** start the desktop tracker — tracker is already running and
    protected by single-instance mutex.
    """
    if not RUN_APP_BAT.is_file():
        raise FileNotFoundError(f"Missing {RUN_APP_BAT}")
    _start_console("CALT API+Frontend", ROOT, "call run.bat")


def launch_calt_stack() -> None:
    """Alias — tray / rules “Start CALT stack” (API + Vite only)."""
    launch_app_fe_be()


def launch_transcript_studio() -> None:
    """Start Transcript Notes Studio GUI."""
    if not STUDIO_BAT.is_file():
        log.warning("Missing %s", STUDIO_BAT)
        return
    _start_console("Transcript Studio", STUDIO_BAT.parent, "call run.bat")


def open_login_page() -> None:
    from backend.behavior.stack_health import open_calt_page

    open_calt_page("/login", speak=True, auto_start=True)
    log.info("Open login (auto-start if stack down)")


def open_tracker_log() -> None:
    """Open desktop_tracker.log in default editor (usually Notepad)."""
    if sys.platform != "win32":
        return
    from backend.behavior.tracker_storage import launcher_log_path, tracker_log_path

    for path in (tracker_log_path(), launcher_log_path()):
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text("", encoding="utf-8")
    try:
        os.startfile(str(tracker_log_path()))  # noqa: S606
        log.info("Opened log %s", tracker_log_path())
    except OSError as exc:
        log.warning("Could not open log: %s", exc)
