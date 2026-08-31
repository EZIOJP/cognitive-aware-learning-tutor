"""Today tab — live gate glance."""

from __future__ import annotations

import webbrowser
from typing import TYPE_CHECKING

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from backend.behavior.calt_desktop.constants import CALENDAR_URL, STUDY_URL

if TYPE_CHECKING:
    from backend.behavior.tracker_service import TrackerService


class TodayTab(QWidget):
    def __init__(self, service: TrackerService) -> None:
        super().__init__()
        self._service = service
        lay = QVBoxLayout(self)
        self._mode = QLabel("Mode: …")
        self._mode.setStyleSheet("font-size: 22px; font-weight: 700;")
        self._focus = QLabel("Focus: …")
        self._morning = QLabel("Morning: …")
        self._stack = QLabel("Stack: …")
        for w in (self._mode, self._focus, self._morning, self._stack):
            w.setWordWrap(True)
            lay.addWidget(w)

        btn_cal = QPushButton("Open calendar (web)")
        btn_cal.clicked.connect(lambda: webbrowser.open(CALENDAR_URL))
        btn_study = QPushButton("Open study app")
        btn_study.clicked.connect(lambda: webbrowser.open(STUDY_URL))
        lay.addWidget(btn_cal)
        lay.addWidget(btn_study)
        lay.addStretch(1)

        self._timer = QTimer(self)
        self._timer.setInterval(5000)
        self._timer.timeout.connect(self.refresh)
        self._timer.start()
        self.refresh()

    def refresh(self) -> None:
        try:
            gate = self._service.latest_gate() or {}
        except Exception:  # noqa: BLE001
            gate = {}
        browser = gate.get("browser") or {}
        mode = browser.get("mode") or gate.get("browser_mode") or "?"
        try:
            from backend.behavior.browser_gate_policy import mode_label

            mode_s = mode_label(str(mode))
        except Exception:  # noqa: BLE001
            mode_s = str(mode)
        self._mode.setText(f"Mode: {mode_s}")

        prod = gate.get("productive_minutes")
        goal = (gate.get("policy") or {}).get("daily_goal_minutes") or gate.get(
            "daily_goal_minutes"
        )
        if prod is None:
            try:
                prod = int((self._service.today_seconds() or 0) // 60)
            except Exception:  # noqa: BLE001
                prod = "?"
        goal_s = goal if goal is not None else "—"
        self._focus.setText(f"Focus: {prod} / {goal_s} productive minutes")

        morning = gate.get("morning") or {}
        nxt = morning.get("next") or "open"
        try:
            from backend.behavior.tracker_rules import next_step_label

            nxt_s = next_step_label(nxt)
        except Exception:  # noqa: BLE001
            nxt_s = str(nxt)
        self._morning.setText(f"Morning next: {nxt_s}")

        try:
            from backend.behavior.stack_health import get_stack_health

            self._stack.setText(get_stack_health().status_line())
        except Exception:  # noqa: BLE001
            self._stack.setText("Stack: ?")
