"""Tabbed main window shell."""

from __future__ import annotations

import webbrowser
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from backend.behavior.calt_desktop.constants import CALENDAR_URL, LOGIN_URL
from backend.behavior.calt_desktop.tabs.rules import RulesTab
from backend.behavior.calt_desktop.tabs.today import TodayTab

if TYPE_CHECKING:
    from backend.behavior.tracker_service import TrackerService


def _placeholder(title: str, body: str) -> QWidget:
    w = QWidget()
    lay = QVBoxLayout(w)
    heading = QLabel(title)
    heading.setStyleSheet("font-size: 18px; font-weight: 600;")
    note = QLabel(body)
    note.setWordWrap(True)
    note.setStyleSheet("color: #94a3b8;")
    lay.addWidget(heading)
    lay.addWidget(note)
    lay.addStretch(1)
    return w


class MainWindow(QMainWindow):
    def __init__(self, service: TrackerService) -> None:
        super().__init__()
        self._service = service
        self.setWindowTitle("CALT Desktop")
        self.resize(960, 640)

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        top = QHBoxLayout()
        title = QLabel("CALT Desktop — Productivity")
        title.setStyleSheet("font-size: 20px; font-weight: 700;")
        top.addWidget(title)
        top.addStretch(1)
        btn_cal = QPushButton("Open calendar (web)")
        btn_cal.clicked.connect(lambda: webbrowser.open(CALENDAR_URL))
        btn_study = QPushButton("Open study login")
        btn_study.clicked.connect(lambda: webbrowser.open(LOGIN_URL))
        top.addWidget(btn_cal)
        top.addWidget(btn_study)
        layout.addLayout(top)

        tabs = QTabWidget()
        tabs.addTab(TodayTab(service), "Today")
        tabs.addTab(
            _placeholder("Bible", "Morning bible reader + mark done — next."),
            "Bible",
        )
        tabs.addTab(
            _placeholder(
                "Plan",
                "Confirm today's plan here next. Full calendar editor stays on the website.",
            ),
            "Plan",
        )
        tabs.addTab(RulesTab(service), "Rules")
        tabs.addTab(
            _placeholder("Schedules", "Freedom-style recurring windows — next."),
            "Schedules",
        )
        tabs.addTab(
            _placeholder("Device", "Hosts / porn / social block — next."),
            "Device",
        )
        tabs.addTab(
            _placeholder("Watch", "CALT Sync hub status + setup — Phase 2."),
            "Watch",
        )
        tabs.addTab(
            _placeholder("Voice", "Voice notes list / play / download — Phase 2."),
            "Voice",
        )
        tabs.addTab(
            _placeholder("Settings", "Stack health, Jarvis, planning prefs — Phase 2."),
            "Settings",
        )
        layout.addWidget(tabs)

        foot = QLabel(
            "CALT Desktop · tracker + hub in this process · "
            "calendar remains at /productivity"
        )
        foot.setAlignment(Qt.AlignmentFlag.AlignLeft)
        foot.setStyleSheet("color: #64748b; font-size: 11px;")
        layout.addWidget(foot)

    def closeEvent(self, event) -> None:  # noqa: N802
        event.ignore()
        self.hide()
