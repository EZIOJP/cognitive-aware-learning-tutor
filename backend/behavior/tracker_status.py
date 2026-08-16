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
    """Windows: count root tracker pythons (ignore multiprocessing children)."""
    if os.name != "nt":
        return 0
    try:
        import psutil
    except ImportError:
        return 0
    procs: list[tuple[int, int]] = []
    for p in psutil.process_iter(["pid", "ppid", "name", "cmdline"]):
        try:
            name = (p.info.get("name") or "").lower()
            if name not in {"python.exe", "pythonw.exe"}:
                continue
            cmd = " ".join(p.info.get("cmdline") or [])
            if "desktop_tracker" not in cmd:
                continue
            procs.append((int(p.info["pid"]), int(p.info.get("ppid") or 0)))
        except (TypeError, ValueError):
            continue
        except Exception:
            continue
    if not procs:
        return 0
    ids = {pid for pid, _ in procs}
    return sum(1 for pid, ppid in procs if ppid not in ids)
