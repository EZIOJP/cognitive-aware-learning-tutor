"""
Desktop Activity Tracker — standalone Windows background service.

Polls foreground window, persists to SQLite + CSV, optional WebSocket mirror.
Single instance via mutex; optional system tray for pause/status.

Run:
    python -m backend.behavior.desktop_tracker

Headless (no console window):
    pythonw -m backend.behavior.desktop_tracker

Fully headless (no tray icon — background only):
    set TRACKER_NO_TRAY=1
    pythonw -m backend.behavior.desktop_tracker
"""
from __future__ import annotations

import logging
import os
import sys

log = logging.getLogger("desktop_tracker")

LOGIN_URL = "http://localhost:5173/login"


def _no_tray() -> bool:
    if os.environ.get("TRACKER_NO_TRAY", "").strip().lower() in ("1", "true", "yes"):
        return True
    return "--no-tray" in sys.argv


def _configure_logging() -> None:
    import os

    is_headless = os.path.basename(sys.executable).lower() == "pythonw.exe"
    handlers: list[logging.Handler] = []
    if not is_headless:
        handlers.append(logging.StreamHandler())
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [desktop_tracker] %(message)s",
        datefmt="%H:%M:%S",
        handlers=handlers or None,
        force=True,
    )
    from backend.behavior.tracker_storage import setup_file_logging

    setup_file_logging()


def main() -> None:
    if sys.platform != "win32":
        print("[desktop_tracker] Windows only.")
        sys.exit(1)

    try:
        import psutil  # noqa: F401
    except ImportError:
        print("[desktop_tracker] Missing dependency: psutil")
        print("  pip install psutil pystray")
        sys.exit(1)

    _configure_logging()

    from backend.behavior.tracker_instance import acquire_single_instance, release_single_instance
    from backend.behavior.tracker_service import TrackerService
    from backend.behavior.tracker_tray import run_headless_loop, run_tray

    if not acquire_single_instance():
        sys.exit(0)

    service = TrackerService()
    service.start()
    mode = "no-tray background" if _no_tray() else "system tray"
    log.info("Desktop tracker started (%s) pid=%s", mode, os.getpid())
    log.info("Web login: %s (default admin / admin123)", LOGIN_URL)

    try:
        if _no_tray():
            run_headless_loop(service)
        else:
            run_tray(service)
    except KeyboardInterrupt:
        pass
    finally:
        service.shutdown()
        release_single_instance()
        log.info("Stopped.")


if __name__ == "__main__":
    main()
