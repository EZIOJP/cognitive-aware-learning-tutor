"""QSystemTrayIcon for CALT Desktop."""

from __future__ import annotations

import logging
import webbrowser
from typing import TYPE_CHECKING

from PySide6.QtGui import QAction, QIcon, QPixmap, QColor
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from backend.behavior.calt_desktop.constants import CALENDAR_URL, LOGIN_URL

if TYPE_CHECKING:
    from backend.behavior.tracker_service import TrackerService
    from backend.behavior.calt_desktop.main_window import MainWindow

log = logging.getLogger("calt_desktop")


def _dot_icon(color: str = "#14b8a6") -> QIcon:
    pm = QPixmap(64, 64)
    pm.fill(QColor("transparent"))
    from PySide6.QtGui import QPainter, QBrush

    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QBrush(QColor(color)))
    p.setPen(QColor("#0f172a"))
    p.drawEllipse(8, 8, 48, 48)
    p.end()
    return QIcon(pm)


class DesktopTray:
    def __init__(
        self,
        service: TrackerService,
        window: MainWindow,
        app: QApplication,
    ) -> None:
        self._service = service
        self._window = window
        self._app = app
        self._tray = QSystemTrayIcon(_dot_icon(), app)
        self._tray.setToolTip("CALT Desktop")
        menu = QMenu()

        act_open = QAction("Open CALT Desktop", menu)
        act_open.triggered.connect(self._show_window)
        menu.addAction(act_open)

        act_cal = QAction("Open calendar (web)", menu)
        act_cal.triggered.connect(lambda: webbrowser.open(CALENDAR_URL))
        menu.addAction(act_cal)

        act_login = QAction("Open study login", menu)
        act_login.triggered.connect(lambda: webbrowser.open(LOGIN_URL))
        menu.addAction(act_login)

        menu.addSeparator()

        act_free = QAction("Free time…", menu)
        act_free.triggered.connect(self._free_time_stub)
        menu.addAction(act_free)

        menu.addSeparator()

        act_restart = QAction("Restart tracker…", menu)
        act_restart.triggered.connect(self._restart)
        menu.addAction(act_restart)

        act_quit = QAction("Quit", menu)
        act_quit.triggered.connect(self._quit)
        menu.addAction(act_quit)

        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_activated)

    def show(self) -> None:
        self._tray.show()

    def _show_window(self) -> None:
        self._window.show()
        self._window.raise_()
        self._window.activateWindow()

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_window()

    def _free_time_stub(self) -> None:
        QMessageBox.information(
            self._window,
            "Free time",
            "PIN free-time override moves here in Phase 1.\n"
            "Until then use the legacy tray or API override.",
        )

    def _restart(self) -> None:
        reply = QMessageBox.question(
            self._window,
            "Restart",
            "Stop this process and relaunch CALT Desktop?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            from backend.behavior.tracker_restart import flush_before_restart, spawn_restart_detached

            flush_before_restart(self._service)
            # spawn_restart_detached uses legacy tray launcher for now;
            # Phase 3 points it at calt_desktop.
            if not spawn_restart_detached():
                QMessageBox.warning(self._window, "Restart", "Could not spawn restart.")
                return
            self._tray.hide()
            self._app.quit()
        except Exception as exc:  # noqa: BLE001
            log.exception("restart")
            QMessageBox.warning(self._window, "Restart", str(exc))

    def _quit(self) -> None:
        reply = QMessageBox.question(
            self._window,
            "Quit CALT Desktop",
            "Stop tracker, hub, and this window?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._tray.hide()
            self._app.quit()
