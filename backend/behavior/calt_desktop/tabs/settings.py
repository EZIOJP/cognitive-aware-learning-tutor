"""Settings tab — explicit sections for system, planning data, gate, tracker."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from backend.behavior.calt_desktop.navigation import go_tab
from backend.paths import ROOT
from backend.behavior.calt_desktop.widgets.gloss_panel import GlossPanel
from backend.behavior.calt_desktop.widgets.section_header import PhaseBanner, SectionHeader
from backend.behavior.calt_desktop.widgets.system_status_panel import SystemStatusPanel
from backend.behavior.calt_desktop.widgets.tab_lifecycle import VisiblePollMixin
from backend.behavior.calt_desktop.widgets.voice_agent_panel import VoiceAgentPanel
from backend.behavior.calt_desktop.theme import muted_label

if TYPE_CHECKING:
    from backend.behavior.tracker_service import TrackerService

_GOALS_FILE = ROOT / "data" / "behavior" / "productivity_goals.json"


class SettingsTab(VisiblePollMixin, QWidget):
    REFRESH_MS = 25_000

    def __init__(self, service: TrackerService | None = None) -> None:
        super().__init__()
        self._service = service
        lay = QVBoxLayout(self)

        lay.addWidget(
            PhaseBanner(
                "Settings",
                "System health, planning storage, and tracker — not the Plan wizard (use Plan tab).",
            )
        )

        self._status = SystemStatusPanel(service, compact=False, show_checklist=True)
        self._status.stack_ready.connect(self._forward_stack_ready)
        lay.addWidget(self._status)
        self._local_note = muted_label("Local settings below load instantly — health row updates in background.")
        lay.addWidget(self._local_note)

        plan_panel = GlossPanel()
        plan_panel.body_layout().addWidget(
            SectionHeader(
                "Planning data",
                "Goals JSON shared with desktop propose · blocks/routines live in vocab_app.db.",
            )
        )
        self._goals_path = muted_label(str(_GOALS_FILE))
        plan_panel.body_layout().addWidget(self._goals_path)
        self._user_line = muted_label("")
        plan_panel.body_layout().addWidget(self._user_line)
        btn_plan = QPushButton("Open Plan phase")
        btn_plan.clicked.connect(lambda: go_tab("Plan"))
        plan_panel.body_layout().addWidget(btn_plan)
        lay.addWidget(plan_panel)

        gate_panel = GlossPanel()
        gate_panel.body_layout().addWidget(
            SectionHeader("Gate & rules", "Hard block, daily goal minutes, category scores.")
        )
        self._gate_line = muted_label("")
        gate_panel.body_layout().addWidget(self._gate_line)
        btn_rules = QPushButton("Open Rules tab")
        btn_rules.clicked.connect(lambda: go_tab("Rules"))
        btn_sched = QPushButton("Open Schedules tab")
        btn_sched.clicked.connect(lambda: go_tab("Schedules"))
        gate_panel.body_layout().addWidget(btn_rules)
        gate_panel.body_layout().addWidget(btn_sched)
        lay.addWidget(gate_panel)

        tr_panel = GlossPanel()
        tr_panel.body_layout().addWidget(
            SectionHeader("Tracker", "Desktop process · Jarvis voice agent.")
        )
        self._voice = VoiceAgentPanel(service)
        tr_panel.body_layout().addWidget(self._voice)
        self._env = muted_label("")
        tr_panel.body_layout().addWidget(self._env)
        row_tr = QHBoxLayout()
        btn_log = QPushButton("Open tracker log")
        btn_log.clicked.connect(self._open_log)
        row_tr.addWidget(btn_log)
        btn_web = QPushButton("Open web app")
        btn_web.clicked.connect(self._open_web)
        row_tr.addWidget(btn_web)
        row_tr.addStretch(1)
        tr_panel.body_layout().addLayout(row_tr)
        lay.addWidget(tr_panel)
        lay.addStretch(1)

        self._init_visible_poll()

    @staticmethod
    def _forward_stack_ready() -> None:
        from PySide6.QtWidgets import QApplication, QMessageBox

        win = QApplication.activeWindow()
        if win is not None and hasattr(win, "_on_stack_ready"):
            win._on_stack_ready()  # type: ignore[attr-defined]
            return
        QMessageBox.information(
            None,
            "CALT stack",
            "API and web app are up — open Lecture Notes or sign in from the web UI.",
        )

    def _open_log(self) -> None:
        try:
            from backend.behavior.tracker_launchers import open_tracker_log

            open_tracker_log()
        except Exception as exc:  # noqa: BLE001
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.warning(self.window(), "Tracker log", str(exc))

    def _open_web(self) -> None:
        try:
            from backend.behavior.stack_health import open_calt_page

            open_calt_page("/", speak=False, auto_start=True)
        except Exception as exc:  # noqa: BLE001
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.warning(self.window(), "Web app", str(exc))

    def refresh(self) -> None:
        self._status.refresh()
        uid = 0
        gate_s = "—"
        if self._service is not None:
            uid = int(getattr(self._service, "user_id", 0) or 0)
            try:
                gate = self._service.latest_gate() or {}
                morning = gate.get("morning") or {}
                gate_s = f"next={morning.get('next', '?')} · plan_ok={morning.get('plan_confirmed')}"
            except Exception:  # noqa: BLE001
                pass
        self._user_line.setText(f"Tracker user_id: {uid or 'not linked'}")
        self._gate_line.setText(f"Morning gate: {gate_s}")
        self._goals_path.setText(
            f"Goals file: {_GOALS_FILE} "
            f"({'exists' if _GOALS_FILE.is_file() else 'missing — set in Plan step 2'})"
        )
        self._env.setText(
            f"CALT_DESKTOP={os.environ.get('CALT_DESKTOP', '')} · "
            f"pid={os.getpid()}"
        )
        if hasattr(self, "_voice"):
            self._voice.refresh()
