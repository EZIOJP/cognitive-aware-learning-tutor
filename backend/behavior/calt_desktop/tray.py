"""QSystemTrayIcon for CALT Desktop."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtGui import QAction, QIcon, QPixmap, QColor
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from backend.behavior.calt_desktop.navigation import go_tab

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

        for tab, label in (
            ("Today", "Today"),
            ("Bible", "Morning Bible"),
            ("Plan", "Plan wizard"),
            ("Calendar", "2D calendar"),
        ):
            act = QAction(label, menu)
            act.triggered.connect(lambda _c, t=tab: self._go_tab(t))
            menu.addAction(act)

        menu.addSeparator()

        act_free = QAction("Free time…", menu)
        act_free.triggered.connect(self._free_time_stub)
        menu.addAction(act_free)

        act_reward = QAction("Reward day…", menu)
        act_reward.triggered.connect(self._reward_day)
        menu.addAction(act_reward)

        act_voice_chat = QAction("Voice agent (chat)", menu)
        act_voice_chat.triggered.connect(self._voice_chat)
        menu.addAction(act_voice_chat)

        self._act_voice_hotkey = QAction("Voice hotkey: …", menu)
        self._act_voice_hotkey.triggered.connect(self._toggle_voice_hotkey)
        menu.addAction(self._act_voice_hotkey)

        menu.addSeparator()

        act_restart = QAction("Restart tracker…", menu)
        act_restart.triggered.connect(self._restart)
        menu.addAction(act_restart)

        act_force_stack = QAction("Force restart API + web…", menu)
        act_force_stack.triggered.connect(self._force_restart_stack)
        menu.addAction(act_force_stack)

        act_force_full = QAction("Force rebuild + restart everything…", menu)
        act_force_full.triggered.connect(self._force_restart_full)
        menu.addAction(act_force_full)

        act_quit = QAction("Quit", menu)
        act_quit.triggered.connect(self._quit)
        menu.addAction(act_quit)

        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_activated)
        from PySide6.QtCore import QTimer

        self._menu_timer = QTimer()
        self._menu_timer.setInterval(5000)
        self._menu_timer.timeout.connect(self._refresh_voice_menu_label)
        self._menu_timer.start()
        self._refresh_voice_menu_label()
        self._kill_toast = None

    def _refresh_voice_menu_label(self) -> None:
        try:
            from backend.behavior.voice_agent import (
                is_free_mode_paused,
                is_voice_hotkey_enabled,
                voice_agent_enabled,
            )

            if not voice_agent_enabled():
                self._act_voice_hotkey.setText("Voice hotkey: OFF (env)")
            elif is_free_mode_paused():
                self._act_voice_hotkey.setText("Voice hotkey: OFF (free mode)")
            elif is_voice_hotkey_enabled():
                self._act_voice_hotkey.setText("Voice hotkey: ON")
            else:
                self._act_voice_hotkey.setText("Voice hotkey: OFF")
        except Exception:  # noqa: BLE001
            self._act_voice_hotkey.setText("Voice hotkey: ?")

    def _voice_chat(self) -> None:
        self._show_window()
        try:
            from backend.behavior.voice_agent import open_voice_chat

            open_voice_chat(self._service.user_id)
        except Exception as exc:  # noqa: BLE001
            log.warning("Voice chat failed: %s", exc)

    def _toggle_voice_hotkey(self) -> None:
        try:
            from backend.behavior.voice_agent import (
                is_voice_hotkey_enabled,
                set_voice_hotkey_enabled,
            )

            want = not is_voice_hotkey_enabled()
            set_voice_hotkey_enabled(want, user_id=self._service.user_id)
            self._refresh_voice_menu_label()
        except Exception as exc:  # noqa: BLE001
            log.warning("Voice hotkey toggle failed: %s", exc)

    def show(self) -> None:
        self._tray.show()
        if self._kill_toast is None:
            try:
                from backend.behavior.calt_desktop.kill_log_toast import KillLogToastWatcher

                self._kill_toast = KillLogToastWatcher(self._tray, parent=self._tray)
            except Exception as exc:  # noqa: BLE001
                log.debug("kill toast watcher: %s", exc)

    def _show_window(self) -> None:
        self._window.show()
        self._window.raise_()
        self._window.activateWindow()

    def _go_tab(self, tab: str) -> None:
        self._show_window()
        go_tab(tab)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_window()

    def _free_time_stub(self) -> None:
        from backend.behavior.calt_desktop.dialogs import prompt_free_time

        prompt_free_time(self._window)

    def _reward_day(self) -> None:
        self._show_window()
        go_tab("Today")

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
            if not spawn_restart_detached():
                QMessageBox.warning(self._window, "Restart", "Could not spawn restart.")
                return
            self._tray.hide()
            self._app.quit()
        except Exception as exc:  # noqa: BLE001
            log.exception("restart")
            QMessageBox.warning(self._window, "Restart", str(exc))

    def _force_restart_stack(self) -> None:
        reply = QMessageBox.question(
            self._window,
            "Force restart API + web",
            "Kill and restart the API (:8000) and Vite (:5173) even if they look healthy.\n"
            "Tracker stays up. A console window will show progress.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            from backend.behavior.force_stack_restart import spawn_force_restart

            if not spawn_force_restart(mode="stack", rebuild=False):
                QMessageBox.warning(self._window, "Force restart", "Could not spawn force restart.")
        except Exception as exc:  # noqa: BLE001
            log.exception("force stack restart")
            QMessageBox.warning(self._window, "Force restart", str(exc))

    def _force_restart_full(self) -> None:
        reply = QMessageBox.question(
            self._window,
            "Force rebuild + restart everything",
            "1) npm run build\n"
            "2) Force restart API + Vite\n"
            "3) Restart this tracker\n\n"
            "Use after code changes when smart restart skipped healthy-but-stale servers.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            from backend.behavior.force_stack_restart import spawn_force_restart
            from backend.behavior.tracker_restart import flush_before_restart

            flush_before_restart(self._service)
            if not spawn_force_restart(mode="full", rebuild=True, then_tracker=True):
                QMessageBox.warning(self._window, "Force full", "Could not spawn force full restart.")
                return
            # Detached worker restarts tracker after servers; quit this instance
            # so the relaunch does not fight the single-instance lock.
            self._tray.hide()
            self._app.quit()
        except Exception as exc:  # noqa: BLE001
            log.exception("force full restart")
            QMessageBox.warning(self._window, "Force full", str(exc))

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
