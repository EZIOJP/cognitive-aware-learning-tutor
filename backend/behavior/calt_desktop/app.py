"""Bootstrap QApplication + TrackerService + tray."""

from __future__ import annotations

import logging
import os
import sys

log = logging.getLogger("calt_desktop")


def _configure_logging() -> None:
    is_headless = os.path.basename(sys.executable).lower() == "pythonw.exe"
    handlers: list[logging.Handler] = []
    if not is_headless:
        handlers.append(logging.StreamHandler())
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [calt_desktop] %(message)s",
        datefmt="%H:%M:%S",
        handlers=handlers or None,
        force=True,
    )
    try:
        from backend.behavior.tracker_storage import setup_file_logging

        setup_file_logging()
    except Exception as exc:  # noqa: BLE001
        log.debug("file logging skipped: %s", exc)


def run() -> int:
    if sys.platform != "win32":
        print("[calt_desktop] Windows only for now.")
        return 1

    if os.environ.get("CALT_TRACKER_PRIMARY") == "1":
        return 0

    from backend.behavior.tracker_instance import acquire_single_instance, release_single_instance

    if not acquire_single_instance():
        log.info("Another tracker/desktop instance already holds the mutex — exit.")
        return 0
    os.environ["CALT_TRACKER_PRIMARY"] = "1"
    # Desktop owns the tray; prevent nested pystray path if anything re-enters.
    os.environ["TRACKER_NO_TRAY"] = "1"
    os.environ["CALT_DESKTOP"] = "1"

    try:
        import psutil  # noqa: F401
    except ImportError:
        release_single_instance()
        print("[calt_desktop] Missing dependency: psutil")
        return 1

    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        release_single_instance()
        print("[calt_desktop] Missing dependency: PySide6")
        print("  pip install PySide6")
        return 1

    _configure_logging()

    from backend.behavior.tracker_service import TrackerService

    from backend.behavior.calt_desktop.constants import CALENDAR_URL, LOGIN_URL
    from backend.behavior.calt_desktop.main_window import MainWindow
    from backend.behavior.calt_desktop.tray import DesktopTray

    qt_app = QApplication(sys.argv)
    qt_app.setQuitOnLastWindowClosed(False)
    qt_app.setApplicationName("CALT Desktop")
    qt_app.setOrganizationName("CALT")

    service = TrackerService()
    service.start()
    log.info("TrackerService started under CALT Desktop pid=%s", os.getpid())
    log.info("Web login: %s · calendar: %s", LOGIN_URL, CALENDAR_URL)

    window = MainWindow(service)
    tray = DesktopTray(service, window, qt_app)
    tray.show()
    window.show()

    code = 0
    try:
        code = int(qt_app.exec())
    except KeyboardInterrupt:
        code = 0
    finally:
        try:
            service.shutdown()
        except Exception as exc:  # noqa: BLE001
            log.warning("service shutdown: %s", exc)
        release_single_instance()
        log.info("Stopped.")
    return code
