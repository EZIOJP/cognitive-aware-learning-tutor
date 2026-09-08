"""Main window — left sidebar + stacked content."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from backend.behavior.calt_desktop.desktop_prefs import (
    load_last_tab,
    restore_window_geometry,
    save_last_tab,
    save_window_geometry,
)
from backend.behavior.calt_desktop.navigation import TAB_NAMES, navigator
from backend.behavior.calt_desktop.tabs.bible import BibleTab
from backend.behavior.calt_desktop.tabs.calendar import CalendarTab
from backend.behavior.calt_desktop.tabs.device import DeviceTab
from backend.behavior.calt_desktop.tabs.plan import PlanTab
from backend.behavior.calt_desktop.tabs.rules import RulesTab
from backend.behavior.calt_desktop.tabs.schedules import SchedulesTab
from backend.behavior.calt_desktop.tabs.settings import SettingsTab
from backend.behavior.calt_desktop.tabs.today import TodayTab
from backend.behavior.calt_desktop.tabs.voice import VoiceTab
from backend.behavior.calt_desktop.tabs.watch import WatchTab
from backend.behavior.calt_desktop.theme import apply_calt_theme
from backend.behavior.calt_desktop.widgets.sidebar_nav import SidebarNav
from backend.behavior.calt_desktop.widgets.tab_lifecycle import DeferredTab
from backend.behavior.calt_desktop.widgets.webview_dashboard import WebViewDashboard

if TYPE_CHECKING:
    from backend.behavior.tracker_service import TrackerService


class MainWindow(QMainWindow):
    def __init__(self, service: TrackerService) -> None:
        super().__init__()
        self._service = service
        self.setWindowTitle("CALT Desktop · Focus")
        restore_window_geometry(self)
        if self.width() < 400:
            self.resize(1100, 720)
        apply_calt_theme(self)

        navigator().tab_requested.connect(self._on_tab_requested)

        shell = QWidget()
        root = QHBoxLayout(shell)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._sidebar = SidebarNav()
        self._sidebar.tab_selected.connect(self._on_sidebar_tab)
        self._sidebar.stack_control.stack_ready.connect(self._on_stack_ready)
        root.addWidget(self._sidebar)

        content = QWidget()
        content_lay = QVBoxLayout(content)
        content_lay.setContentsMargins(14, 14, 14, 10)
        content_lay.setSpacing(0)

        self._pages = QStackedWidget()
        self._pages.addWidget(WebViewDashboard(service))
        self._pages.addWidget(TodayTab(service))
        self._pages.addWidget(DeferredTab(lambda: PlanTab(service)))
        self._pages.addWidget(DeferredTab(lambda: BibleTab(service)))
        self._pages.addWidget(DeferredTab(lambda: CalendarTab(service)))
        self._pages.addWidget(DeferredTab(lambda: RulesTab(service)))
        self._pages.addWidget(DeferredTab(lambda: SchedulesTab()))
        self._pages.addWidget(DeferredTab(lambda: DeviceTab()))
        self._pages.addWidget(DeferredTab(lambda: WatchTab()))
        self._pages.addWidget(DeferredTab(lambda: VoiceTab()))
        self._pages.addWidget(DeferredTab(lambda: SettingsTab(service)))
        content_lay.addWidget(self._pages, stretch=1)
        root.addWidget(content, stretch=1)

        self.setCentralWidget(shell)

        last = load_last_tab("Dashboard")
        if last in TAB_NAMES:
            self.navigate_to(last, show=False)

        QTimer.singleShot(2500, self._warm_deferred_tabs)
        self._install_tab_shortcuts()

    def _install_tab_shortcuts(self) -> None:
        for idx, key in enumerate("123456789"):
            if idx >= len(TAB_NAMES):
                break
            sc = QShortcut(QKeySequence(f"Ctrl+{key}"), self)
            sc.activated.connect(lambda i=idx: self.navigate_to(TAB_NAMES[i], show=False))
        if len(TAB_NAMES) >= 10:
            sc0 = QShortcut(QKeySequence("Ctrl+0"), self)
            sc0.activated.connect(lambda: self.navigate_to(TAB_NAMES[9], show=False))

    def _on_stack_ready(self) -> None:
        QMessageBox.information(
            self,
            "CALT stack",
            "API and web app are up — open Lecture Notes or sign in from the web UI.",
        )

    def _on_sidebar_tab(self, name: str) -> None:
        self.navigate_to(name, show=False)

    def navigate_to(self, tab: str, *, show: bool = True) -> None:
        if tab not in TAB_NAMES:
            return
        idx = TAB_NAMES.index(tab)
        self._pages.setCurrentIndex(idx)
        self._sidebar.set_current_tab(tab)
        save_last_tab(tab)
        self._refresh_tab_at(idx)
        if show:
            self.show()
            self.raise_()
            self.activateWindow()

    def _on_tab_requested(self, payload: str) -> None:
        show = True
        name = payload
        if payload.startswith("::"):
            show = False
            name = payload[2:]
        self.navigate_to(name, show=show)

    def _refresh_tab_at(self, index: int) -> None:
        w = self._pages.widget(index)
        if w is None:
            return
        if hasattr(w, "ensure"):
            content = w.ensure()
            if content is not None and hasattr(content, "refresh"):
                content.refresh()
        elif hasattr(w, "refresh"):
            w.refresh()

    def _warm_deferred_tabs(self) -> None:
        # Bible + Calendar (indices shift when Dashboard is first)
        for idx in (3, 4):
            w = self._pages.widget(idx)
            if isinstance(w, DeferredTab):
                w.warm()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._sidebar.stack_control.set_active(True)
        QTimer.singleShot(0, lambda: self._refresh_tab_at(self._pages.currentIndex()))

    def hideEvent(self, event) -> None:  # noqa: N802
        super().hideEvent(event)
        save_window_geometry(self)
        self._sidebar.stack_control.set_active(False)

    def closeEvent(self, event) -> None:  # noqa: N802
        event.ignore()
        self.hide()
