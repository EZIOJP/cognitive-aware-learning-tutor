"""Keepalive check for desktop tracker — run under pythonw (no console)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts" / "desktop_tracker"
VBS = SCRIPTS / "tracker_tray_launch.vbs"
LOCK = ROOT / "data" / "logs" / "tracker_keepalive.launch.lock"
MUTEX_NAMES = (
    r"Local\CognitiveAwareTutor.DesktopTracker",
    r"Global\CognitiveAwareTutor.DesktopTracker",
)


def _mutex_held() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        OpenMutexW = kernel32.OpenMutexW
        OpenMutexW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
        OpenMutexW.restype = wintypes.HANDLE
        for name in MUTEX_NAMES:
            h = OpenMutexW(0x00100000, False, name)
            if h:
                kernel32.CloseHandle(h)
                return True
    except Exception:
        return False
    return False


def _root_tracker_count() -> int:
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
            if "desktop_tracker" not in cmd and "calt_desktop" not in cmd:
                continue
            if "tracker_keepalive" in cmd or "tracker_restart" in cmd:
                continue
            procs.append((int(p.info["pid"]), int(p.info.get("ppid") or 0)))
        except (psutil.Error, TypeError, ValueError):
            continue
    if not procs:
        return 0
    ids = {pid for pid, _ in procs}
    return sum(1 for pid, ppid in procs if ppid not in ids)


def _launch_lock_ok() -> bool:
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    import time

    now = time.time()
    if LOCK.is_file():
        try:
            if now - LOCK.stat().st_mtime < 45:
                return False
        except OSError:
            return False
    try:
        LOCK.write_text(str(os.getpid()), encoding="utf-8")
    except OSError:
        return False
    return True


def _pythonw() -> Path:
    pyw = ROOT / ".venv" / "Scripts" / "pythonw.exe"
    if pyw.is_file():
        return pyw
    py = ROOT / ".venv" / "Scripts" / "python.exe"
    return py if py.is_file() else Path("pythonw")


def main() -> int:
    if _mutex_held() or _root_tracker_count() >= 1:
        return 0
    if not _launch_lock_ok():
        return 0
    if _root_tracker_count() >= 1:
        return 0
    if not VBS.is_file():
        return 1
    py = _pythonw()
    creation = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    subprocess.Popen(
        ["wscript.exe", "//B", str(VBS), str(py)],
        cwd=str(ROOT),
        creationflags=creation,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
