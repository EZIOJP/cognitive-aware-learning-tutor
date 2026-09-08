"""Single dynamic control for CALT stack status + start/run actions."""

from __future__ import annotations

from PySide6.QtCore import QTimer, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QPushButton, QVBoxLayout, QWidget

from backend.behavior.calt_desktop.system_status import collect_system_status


class StackControl(QWidget):
    """Shows API/Web/Hub status; one click starts or opens stack actions."""

    stack_ready = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._active = True
        self._waiting_stack = False
        self._was_stack_up = False
        self._starting = False

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self._btn = QPushButton("Checking stack…")
        self._btn.setObjectName("stackControl")
        self._btn.clicked.connect(self._on_click)
        lay.addWidget(self._btn)

        self._timer = QTimer(self)
        self._timer.setInterval(12_000)
        self._timer.timeout.connect(self.refresh)

        self._ready_poll = QTimer(self)
        self._ready_poll.setInterval(2500)
        self._ready_poll.timeout.connect(self._poll_stack_ready)
        self._poll_interval_up_ms = 12_000
        self._poll_interval_down_ms = 30_000

    def set_active(self, active: bool) -> None:
        self._active = active
        if active:
            self._timer.start()
            QTimer.singleShot(0, self.refresh)
        else:
            self._timer.stop()
            self._ready_poll.stop()

    def refresh(self) -> None:
        if not self._active:
            return
        st = collect_system_status()
        if st.get("stack_up"):
            self._was_stack_up = True
        self._apply_status(st)

    def _poll_stack_ready(self) -> None:
        st = collect_system_status()
        if st.get("stack_up"):
            self._ready_poll.stop()
            self._starting = False
            if self._waiting_stack and not self._was_stack_up:
                self.stack_ready.emit()
            self._waiting_stack = False
            self._was_stack_up = True
        self._apply_status(st)

    def _status_bits(self, st: dict) -> str:
        def bit(name: str, key: str) -> str:
            return f"{name} {'up' if st.get(key) else 'down'}"

        return f"{bit('API', 'api_up')} · {bit('Web', 'web_up')} · {bit('Hub', 'hub_up')}"

    def _apply_status(self, st: dict) -> None:
        bits = self._status_bits(st)
        stack_up = bool(st.get("stack_up"))
        api_up = bool(st.get("api_up"))

        if self._starting:
            self._btn.setText(f"Starting CALT stack…\n{bits}")
            self._btn.setProperty("stackState", "starting")
            self._btn.setEnabled(False)
        elif stack_up:
            self._btn.setText(f"CALT stack running\n{bits}")
            self._btn.setProperty("stackState", "up")
            self._btn.setEnabled(True)
        elif api_up:
            self._btn.setText(f"Start web (Vite)\n{bits}")
            self._btn.setProperty("stackState", "partial")
            self._btn.setEnabled(True)
        else:
            self._btn.setText(f"Run CALT stack\n{bits}")
            self._btn.setProperty("stackState", "down")
            self._btn.setEnabled(True)

        self._btn.style().unpolish(self._btn)
        self._btn.style().polish(self._btn)

        # Slow polls while web is down to avoid CLOSE_WAIT pile-up on hung Vite.
        want_ms = (
            self._poll_interval_up_ms
            if st.get("web_up")
            else self._poll_interval_down_ms
        )
        if self._timer.interval() != want_ms:
            self._timer.setInterval(want_ms)

    def _on_click(self) -> None:
        st = collect_system_status()
        if st.get("stack_up"):
            self._show_up_menu()
        elif st.get("api_up"):
            self._run_full_stack()
        else:
            self._run_full_stack()

    def _show_up_menu(self) -> None:
        menu = QMenu(self)
        open_web = QAction("Open web app", self)
        open_web.triggered.connect(lambda: self._open_page("/"))
        menu.addAction(open_web)
        login = QAction("Open sign-in", self)
        login.triggered.connect(lambda: self._open_page("/login"))
        menu.addAction(login)
        menu.addSeparator()
        restart = QAction("Restart stack (smart — only if down)", self)
        restart.triggered.connect(self._run_full_stack)
        menu.addAction(restart)
        force = QAction("Force restart API + web…", self)
        force.triggered.connect(self._force_restart_stack)
        menu.addAction(force)
        force_full = QAction("Force rebuild + restart everything…", self)
        force_full.triggered.connect(self._force_restart_full)
        menu.addAction(force_full)
        menu.exec(self._btn.mapToGlobal(self._btn.rect().bottomLeft()))

    def _force_restart_stack(self) -> None:
        try:
            from backend.behavior.force_stack_restart import spawn_force_restart

            if spawn_force_restart(mode="stack", rebuild=False):
                self._starting = True
                self._waiting_stack = True
                self._ready_poll.start()
                self._btn.setText("Force-restarting API + web…")
                self.refresh()
            else:
                self._btn.setText("Force restart failed to spawn")
        except Exception as exc:  # noqa: BLE001
            self._btn.setText(f"Force restart failed\n{exc}"[:80])
        finally:
            QTimer.singleShot(8000, self.refresh)

    def _force_restart_full(self) -> None:
        try:
            from backend.behavior.force_stack_restart import spawn_force_restart

            # Tracker will quit/relaunch after servers; this process may die.
            if not spawn_force_restart(mode="full", rebuild=True, then_tracker=True):
                self._btn.setText("Force full restart failed to spawn")
                return
            self._btn.setText("Force full: build + stack + tracker…")
            self._btn.setEnabled(False)
        except Exception as exc:  # noqa: BLE001
            self._btn.setText(f"Force full failed\n{exc}"[:80])
        finally:
            QTimer.singleShot(8000, self.refresh)

    @staticmethod
    def _open_page(path: str) -> None:
        try:
            from backend.behavior.stack_health import open_calt_page

            open_calt_page(path, speak=False, auto_start=False)
        except Exception:  # noqa: BLE001
            pass

    def _run_full_stack(self) -> None:
        try:
            from backend.behavior.tracker_launchers import launch_calt_stack

            launch_calt_stack(force=True)
            self._waiting_stack = True
            self._starting = True
            self._ready_poll.start()
            self.refresh()
        except Exception as exc:  # noqa: BLE001
            self._starting = False
            self._btn.setText(f"Launch failed\n{exc}"[:80])
            self._btn.setEnabled(True)
        finally:
            QTimer.singleShot(5000, self.refresh)

    def _start_api_only(self) -> None:
        try:
            from backend.behavior.stack_health import get_stack_health, start_calt_stack

            if get_stack_health(force=True).api_up:
                self.refresh()
                return
            start_calt_stack(force=True)
            self._waiting_stack = True
            self._starting = True
            self._ready_poll.start()
            self.refresh()
        except Exception as exc:  # noqa: BLE001
            self._starting = False
            self._btn.setText(f"API start failed\n{exc}"[:80])
        finally:
            QTimer.singleShot(5000, self.refresh)
