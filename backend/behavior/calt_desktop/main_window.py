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
from backend.behavior.calt_desktop.tabs.bible import BibleTab
from backend.behavior.calt_desktop.tabs.device import DeviceTab
from backend.behavior.calt_desktop.tabs.plan import PlanTab
from backend.behavior.calt_desktop.tabs.rules import RulesTab
from backend.behavior.calt_desktop.tabs.schedules import SchedulesTab
from backend.behavior.calt_desktop.tabs.settings import SettingsTab
from backend.behavior.calt_desktop.tabs.today import TodayTab
from backend.behavior.calt_desktop.tabs.voice import VoiceTab
from backend.behavior.calt_desktop.tabs.watch import WatchTab

if TYPE_CHECKING:
    from backend.behavior.tracker_service import TrackerService


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
        tabs.addTab(BibleTab(service), "Bible")
        tabs.addTab(PlanTab(service), "Plan")
        tabs.addTab(RulesTab(service), "Rules")
        tabs.addTab(SchedulesTab(), "Schedules")
        tabs.addTab(DeviceTab(), "Device")
        tabs.addTab(WatchTab(), "Watch")
        tabs.addTab(VoiceTab(), "Voice")
        tabs.addTab(SettingsTab(), "Settings")
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
