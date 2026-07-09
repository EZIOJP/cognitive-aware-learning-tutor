"""Live tracker process signals (independent of DB last_event_at)."""

from __future__ import annotations

import os
import time
from pathlib import Path

from backend.behavior.tracker_storage import CHECKPOINT_PATH, tracker_log_path

CHECKPOINT_FRESH_SECONDS = 120
LOG_FRESH_SECONDS = 180


def _mtime_age_s(path: Path) -> float | None:
    try:
        if not path.is_file():
            return None
        return time.time() - path.stat().st_mtime
    except OSError:
        return None


def tracker_process_recently_active() -> bool:
    """True when standalone tracker checkpoint or log was updated recently."""
    cp_age = _mtime_age_s(CHECKPOINT_PATH)
    if cp_age is not None and cp_age < CHECKPOINT_FRESH_SECONDS:
        return True
    log_age = _mtime_age_s(tracker_log_path())
    return log_age is not None and log_age < LOG_FRESH_SECONDS


def tracker_process_detail() -> dict:
    cp_age = _mtime_age_s(CHECKPOINT_PATH)
    log_age = _mtime_age_s(tracker_log_path())
    alive = (
        (cp_age is not None and cp_age < CHECKPOINT_FRESH_SECONDS)
        or (log_age is not None and log_age < LOG_FRESH_SECONDS)
    )
    return {
        "process_alive": alive,
        "checkpoint_age_s": round(cp_age) if cp_age is not None else None,
        "log_age_s": round(log_age) if log_age is not None else None,
    }


def count_tracker_processes() -> int:
    """Windows: count python processes running desktop_tracker (duplicates cause odd flush behavior)."""
    if os.name != "nt":
        return 0
    try:
        import subprocess

        out = subprocess.check_output(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | "
                "Where-Object { ($_.Name -eq 'python.exe' -or $_.Name -eq 'pythonw.exe') "
                "-and $_.CommandLine -match 'desktop_tracker' }).Count",
            ],
            text=True,
            timeout=8,
        )
        return int(out.strip() or "0")
    except (OSError, ValueError, subprocess.SubprocessError):
        return 0
