"""Desktop tracker restart — one code path for bat + tray (reloads Python, keeps storage).

SQLite sessions, CSV logs, and tracker config are **not** deleted. Only the process
is replaced. Tray/menu restarts flush the open session first.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
from pathlib import Path

from backend.paths import ROOT

log = logging.getLogger("desktop_tracker")

VBS = ROOT / "scripts" / "desktop_tracker" / "tracker_tray_launch.vbs"
LAUNCH_LOCK = ROOT / "data" / "logs" / "tracker_restart.launch.lock"

# Shared confirm text (tray subprocess + optional direct use)
CONFIRM_TITLE = "CALT Tracker — Restart"
CONFIRM_TEXT = (
    "Restart the desktop tracker?\n\n"
    "Reloads Python code from disk. Your activity history (SQLite/CSV) is kept.\n"
    "Tracking pauses briefly while a fresh tray instance starts."
)


def _python_exe() -> Path:
    py = ROOT / ".venv" / "Scripts" / "python.exe"
    return py if py.is_file() else Path(sys.executable)


def _pythonw() -> Path:
    pyw = ROOT / ".venv" / "Scripts" / "pythonw.exe"
    if pyw.is_file():
        return pyw
    return _python_exe()


def _tracker_processes() -> list[tuple[int, int]]:
    try:
        import psutil
    except ImportError:
        return []
    out: list[tuple[int, int]] = []
    for proc in psutil.process_iter(["pid", "ppid", "name", "cmdline"]):
        try:
            name = (proc.info.get("name") or "").lower()
            if name not in {"python.exe", "pythonw.exe"}:
                continue
            cmd = " ".join(proc.info.get("cmdline") or [])
            if "desktop_tracker" not in cmd:
                continue
            out.append((int(proc.info["pid"]), int(proc.info.get("ppid") or 0)))
        except (psutil.Error, TypeError, ValueError):
            continue
    return out


def root_tracker_count(*, ignore_pid: int | None = None) -> int:
    procs = [(pid, ppid) for pid, ppid in _tracker_processes() if ignore_pid is None or pid != ignore_pid]
    if not procs:
        return 0
    ids = {pid for pid, _ in procs}
    return sum(1 for pid, ppid in procs if ppid not in ids)


def mutex_held() -> bool:
    from backend.behavior.tracker_instance import LEGACY_MUTEX_NAMES, MUTEX_NAME

    if sys.platform != "win32":
        return False
    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        OpenMutexW = kernel32.OpenMutexW
        OpenMutexW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
        OpenMutexW.restype = wintypes.HANDLE
        for name in (MUTEX_NAME, *LEGACY_MUTEX_NAMES):
            handle = OpenMutexW(0x00100000, False, name)
            if handle:
                kernel32.CloseHandle(handle)
                return True
    except Exception:  # noqa: BLE001
        return False
    return False


def wait_until_clear(*, timeout_s: float = 25.0, wait_pid: int | None = None) -> bool:
    deadline = time.time() + max(1.0, timeout_s)
    while time.time() < deadline:
        if wait_pid is not None:
            try:
                import psutil

                if psutil.pid_exists(wait_pid):
                    time.sleep(0.2)
                    continue
            except Exception:  # noqa: BLE001
                wait_pid = None
        if root_tracker_count() == 0 and not mutex_held():
            return True
        time.sleep(0.25)
    return root_tracker_count() == 0 and not mutex_held()


def kill_all_trackers() -> int:
    killed = 0
    for pid, _ in _tracker_processes():
        try:
            import psutil

            psutil.Process(pid).kill()
            killed += 1
        except Exception:  # noqa: BLE001
            continue
    return killed


def _launch_lock_ok(*, force: bool = False) -> bool:
    if force:
        return True
    LAUNCH_LOCK.parent.mkdir(parents=True, exist_ok=True)
    now = time.time()
    if LAUNCH_LOCK.is_file():
        try:
            if now - LAUNCH_LOCK.stat().st_mtime < 5:
                return False
        except OSError:
            return False
    try:
        LAUNCH_LOCK.write_text(str(os.getpid()), encoding="utf-8")
    except OSError:
        return False
    return True


def launch_tray_tracker(*, force: bool = False) -> bool:
    if sys.platform != "win32":
        return False
    if not VBS.is_file():
        log.error("Missing %s", VBS)
        return False
    if not _launch_lock_ok(force=force):
        log.warning("Restart launch skipped — recent launch lock")
        return False
    if root_tracker_count() >= 1 or mutex_held():
        log.warning("Restart launch skipped — tracker still running")
        return False
    py = _pythonw()
    creation = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        subprocess.Popen(
            ["wscript.exe", "//B", str(VBS), str(py)],
            cwd=str(ROOT),
            creationflags=creation,
        )
        log.info("Launched desktop tracker (fresh Python process) via %s", VBS.name)
        return True
    except OSError as exc:
        log.error("Could not launch tracker: %s", exc)
        return False


def run_restart(*, timeout_s: float = 25.0) -> int:
    """Single restart implementation — used by bat and tray spawn."""
    log.info("Restart go — stop all desktop_tracker PIDs, wait, relaunch")
    kill_all_trackers()
    if not wait_until_clear(timeout_s=timeout_s):
        log.error("Restart failed — tracker still present after kill")
        return 1
    time.sleep(0.5)
    return 0 if launch_tray_tracker(force=True) else 1


def show_confirm_dialog() -> bool:
    """MessageBox / PIN on **this** process main thread (run via subprocess from tray)."""
    from backend.behavior.tracker_exit import exit_confirmation_required, prompt_exit_secret_cli

    if sys.platform != "win32":
        return True

    if exit_confirmation_required():
        ok = prompt_exit_secret_cli(reason="restart the desktop tracker")
        log.info("Restart PIN confirm: %s", "yes" if ok else "no")
        return ok

    try:
        import ctypes

        MB_YESNO = 0x00000004
        MB_ICONQUESTION = 0x00000020
        MB_TOPMOST = 0x00040000
        MB_SETFOREGROUND = 0x00010000
        MB_SYSTEMMODAL = 0x00001000
        IDYES = 6
        rc = ctypes.windll.user32.MessageBoxW(  # type: ignore[attr-defined]
            None,
            CONFIRM_TEXT,
            CONFIRM_TITLE,
            MB_YESNO | MB_ICONQUESTION | MB_TOPMOST | MB_SETFOREGROUND | MB_SYSTEMMODAL,
        )
        ok = rc == IDYES
        log.info("Restart dialog: %s", "yes" if ok else "no")
        return ok
    except Exception as exc:  # noqa: BLE001
        log.warning("Restart dialog failed (%s)", exc)
        return False


def confirm_restart_subprocess() -> bool:
    """Tray-safe confirm — separate python.exe process owns the MessageBox."""
    if sys.platform != "win32":
        return True
    py = _python_exe()
    try:
        rc = subprocess.call(
            [str(py), "-m", "backend.behavior.tracker_restart", "confirm"],
            cwd=str(ROOT),
        )
        return rc == 0
    except OSError as exc:
        log.warning("Restart confirm subprocess failed: %s", exc)
        return False


def spawn_restart_detached() -> bool:
    """Detached ``go`` — same entry point as restart_desktop_tracker.bat step 2."""
    pyw = _pythonw()
    env = os.environ.copy()
    env["CALT_TRACKER_SKIP_STOP_PIN"] = "1"
    creation = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(
        subprocess, "DETACHED_PROCESS", 0
    )
    try:
        subprocess.Popen(
            [str(pyw), "-m", "backend.behavior.tracker_restart", "go"],
            cwd=str(ROOT),
            env=env,
            creationflags=creation,
            close_fds=True,
        )
        log.info("Spawned detached restart (go)")
        return True
    except OSError as exc:
        log.warning("Detached restart spawn failed: %s", exc)
        return False


def flush_before_restart(service: object | None) -> None:
    if service is None:
        return
    try:
        service.flush_current("restart")  # type: ignore[attr-defined]
        from backend.behavior.tracker_storage import flush_pending_events

        flush_pending_events()
        log.info("Flushed sessions before restart (SQLite/CSV kept)")
    except Exception as exc:  # noqa: BLE001
        log.warning("Pre-restart flush skipped: %s", exc)


def request_tray_restart(service: object | None = None) -> None:
    """Tray menu: confirm (subprocess) → flush → same ``go`` as the bat file."""
    if not confirm_restart_subprocess():
        log.info("Restart cancelled from tray")
        return
    flush_before_restart(service)
    if not spawn_restart_detached():
        log.error("Tray restart failed to spawn")


def _configure_restart_logging() -> None:
    if logging.getLogger("desktop_tracker").handlers:
        return
    from backend.behavior.tracker_storage import setup_file_logging

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [desktop_tracker] %(message)s",
        datefmt="%H:%M:%S",
        force=True,
    )
    setup_file_logging()


def main_cli(argv: list[str] | None = None) -> int:
    _configure_restart_logging()
    args = list(argv if argv is not None else sys.argv[1:])
    cmd = (args[0].lower() if args else "go")

    if cmd == "confirm":
        return 0 if show_confirm_dialog() else 1

    if cmd in ("go", "force", "restart"):
        timeout = 25.0
        if len(args) >= 3 and args[1] in ("--timeout", "-t"):
            timeout = float(args[2])
        return run_restart(timeout_s=timeout)

    if cmd in ("wait-gone", "wait"):
        timeout = 25.0
        if len(args) >= 3 and args[1] in ("--timeout", "-t"):
            timeout = float(args[2])
        return 0 if wait_until_clear(timeout_s=timeout) else 1

    return run_restart()


# Back-compat alias used in older tests/callers
force_restart = run_restart


if __name__ == "__main__":
    raise SystemExit(main_cli())
