"""Launch project scripts from the desktop tracker tray menu."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

from backend.paths import ROOT

log = logging.getLogger("desktop_tracker")

RUN_APP_BAT = ROOT / "run.bat"
STUDIO_BAT = ROOT / "transcript-notes-studio" / "run.bat"
RESTART_TRACKER_BAT = ROOT / "scripts" / "desktop_tracker" / "restart_desktop_tracker.bat"
LOGIN_URL = "http://localhost:5173/login"

_LAUNCH_LOCK = threading.Lock()
_last_stack_launch_at = 0.0
_STACK_LAUNCH_DEBOUNCE_S = float(os.environ.get("CALT_STACK_LAUNCH_DEBOUNCE_S", "90") or "90")
_STACK_LAUNCH_FORCE_DEBOUNCE_S = float(
    os.environ.get("CALT_STACK_LAUNCH_FORCE_DEBOUNCE_S", "20") or "20"
)


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


def launch_calt_stack(*, force: bool = False) -> bool:
    """Alias — tray / rules “Start CALT stack” (API + Vite only).

    Debounces repeated launches while run.bat is still starting. Returns True if
    a new console was opened.
    """
    global _last_stack_launch_at
    try:
        from backend.behavior.stack_health import get_stack_health

        snap = get_stack_health(force=True)
        if snap.web_up and snap.api_up:
            log.info("launch_calt_stack skipped — stack already up")
            return False
    except Exception as exc:  # noqa: BLE001
        log.debug("launch_calt_stack health probe skipped: %s", exc)

    now = time.monotonic()
    gap = _STACK_LAUNCH_FORCE_DEBOUNCE_S if force else _STACK_LAUNCH_DEBOUNCE_S
    with _LAUNCH_LOCK:
        if _last_stack_launch_at and (now - _last_stack_launch_at) < max(5.0, gap):
            log.info(
                "launch_calt_stack debounced (%.0fs since last launch)",
                now - _last_stack_launch_at,
            )
            return False
        _last_stack_launch_at = now
    launch_app_fe_be()
    return True


def launch_transcript_studio() -> None:
    """Start Transcript Notes Studio GUI."""
    if not STUDIO_BAT.is_file():
        log.warning("Missing %s", STUDIO_BAT)
        return
    _start_console("Transcript Studio", STUDIO_BAT.parent, "call run.bat")


def open_login_page() -> None:
    from backend.behavior.stack_health import open_calt_page

    open_calt_page("/profile", speak=True, auto_start=True)
    log.info("Open profile (auto-start if stack down)")


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


def launch_tracker_restart(*, pin_confirmed: bool = False) -> None:
    """Force restart via Python helper (scripts/bats use the same module)."""
    if sys.platform != "win32":
        log.warning("Tracker restart is Windows-only")
        return
    if pin_confirmed:
        os.environ["CALT_TRACKER_SKIP_STOP_PIN"] = "1"
    pyw = ROOT / ".venv" / "Scripts" / "pythonw.exe"
    if not pyw.is_file():
        pyw = Path(sys.executable)
    creation = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        subprocess.Popen(
            [str(pyw), "-m", "backend.behavior.tracker_restart", "go"],
            cwd=str(ROOT),
            creationflags=creation,
        )
        log.info("Spawned force tracker restart")
    except OSError as exc:
        log.warning("Could not restart tracker: %s", exc)
        raise
