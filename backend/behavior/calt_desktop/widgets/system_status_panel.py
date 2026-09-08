"""Unified system health + autostart checklist."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QPushButton, QWidget

from backend.behavior.calt_desktop.system_status import checklist_rows, collect_system_status
from backend.behavior.calt_desktop.theme import muted_label, primary_button
from backend.behavior.calt_desktop.widgets.gloss_panel import GlossPanel

if TYPE_CHECKING:
    from backend.behavior.tracker_service import TrackerService


class SystemStatusPanel(GlossPanel):
    stack_ready = Signal()

    def __init__(
        self,
        service: TrackerService | None = None,
        *,
        compact: bool = False,
        show_checklist: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._compact = compact
        self._waiting_stack = False
        self._was_stack_up = False
        self._check_rows: list[tuple[QLabel, QLabel, QLabel]] = []

        title = QLabel("Health")
        title.setObjectName("sectionTitle")
        if compact:
            title.hide()
        self.body_layout().addWidget(title)

        self._summary = QLabel("Checking…")
        self._summary.setWordWrap(True)
        if compact:
            self._summary.setObjectName("muted")
        self.body_layout().addWidget(self._summary)

        self._check_host = QWidget()
        self._check_grid = QGridLayout(self._check_host)
        self._check_grid.setContentsMargins(0, 0, 0, 0)
        if show_checklist:
            self.body_layout().addWidget(self._check_host)
            for row_i, (label, _ok, _det) in enumerate(checklist_rows({})):
                mark = QLabel("○")
                name = QLabel(label)
                det = muted_label("")
                self._check_grid.addWidget(mark, row_i, 0)
                self._check_grid.addWidget(name, row_i, 1)
                self._check_grid.addWidget(det, row_i, 2)
                self._check_rows.append((mark, name, det))

        if not compact:
            row = QHBoxLayout()
            self._btn_full = primary_button("Run full stack")
            self._btn_full.clicked.connect(self._run_full_stack)
            row.addWidget(self._btn_full)
            self._btn_force = QPushButton("Force restart API+web")
            self._btn_force.clicked.connect(self._force_restart_stack)
            row.addWidget(self._btn_force)
            btn_ext = QPushButton("Extension help")
            btn_ext.clicked.connect(self._extension_help)
            row.addWidget(btn_ext)
            row.addStretch(1)
            self.body_layout().addLayout(row)

        self._poll = QTimer(self)
        self._poll.setInterval(4000)
        self._poll.timeout.connect(self._poll_stack_ready)

    def _run_full_stack(self) -> None:
        try:
            from backend.behavior.tracker_launchers import launch_calt_stack

            launch_calt_stack(force=True)
            self._waiting_stack = True
            self._poll.start()
            self._summary.setText("Starting run.bat (API + Vite)…")
        except Exception as exc:  # noqa: BLE001
            self._summary.setText(f"Launch failed: {exc}")

    def _force_restart_stack(self) -> None:
        try:
            from backend.behavior.force_stack_restart import spawn_force_restart

            if spawn_force_restart(mode="stack", rebuild=False):
                self._waiting_stack = True
                self._poll.start()
                self._summary.setText("Force-restarting API + Vite (console opened)…")
            else:
                self._summary.setText("Force restart failed to spawn")
        except Exception as exc:  # noqa: BLE001
            self._summary.setText(f"Force restart failed: {exc}")

    def _extension_help(self) -> None:
        self._summary.setText(
            "Load CALT Gate + SelfTracker in Edge — SoftLand needs API :8000. "
            "App kills: native calt_enforcer (install_native_enforcer.ps1) or "
            "run_native_enforcer_console.bat."
        )

    def _poll_stack_ready(self) -> None:
        st = collect_system_status(self._service)
        if st.get("stack_up"):
            self._poll.stop()
            if self._waiting_stack and not self._was_stack_up:
                self.stack_ready.emit()
            self._waiting_stack = False
            self._was_stack_up = True
        self._apply_status(st)

    def refresh(self) -> None:
        st = collect_system_status(self._service)
        if st.get("stack_up"):
            self._was_stack_up = True
        self._apply_status(st)

    def _apply_status(self, st: dict) -> None:
        api = "up" if st.get("api_up") else "down"
        web = "up" if st.get("web_up") else "down"
        hub = "up" if st.get("hub_up") else "down"
        ext = "alive" if st.get("extension_alive") else "no ping"
        user = st.get("username") or (f"user #{st['user_id']}" if st.get("user_id") else "not linked")
        gate = st.get("gate_mode") or "—"
        lock = "locked" if st.get("gate_locked") else "open"
        enc = "enforcer on" if st.get("enforcer_owns_kills") else "enforcer off"
        if st.get("native_exe_built") and not st.get("enforcer_owns_kills"):
            enc = "enforcer built/off"
        if st.get("native_service_running") is True and st.get("enforcer_owns_kills"):
            enc = "native service on"
        inc = " · incubation" if st.get("incubation_active") else ""
        kill = st.get("last_kill_log") or ""
        kill_bit = f" · last kill: {kill[:40]}" if kill else ""
        self._summary.setText(
            f"API {api} · Web {web} · Hub {hub} · Extension {ext} · "
            f"{user} · Gate {gate} ({lock}{inc}) · {enc}{kill_bit}"
        )

        rows = checklist_rows(st)
        for i, (mark, name, det) in enumerate(self._check_rows):
            if i >= len(rows):
                break
            label, ok, detail = rows[i]
            name.setText(label)
            det.setText(detail)
            mark.setText("✓" if ok else "○")
            mark.setStyleSheet("color: #34d399;" if ok else "color: #f87171;")

        if hasattr(self, "_btn_full"):
            up = bool(st.get("stack_up"))
            self._btn_full.setEnabled(not up)
            self._btn_full.setText("Stack up" if up else "Run full stack")
