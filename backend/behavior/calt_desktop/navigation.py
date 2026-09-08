"""In-app tab navigation — no browser, no Chromium, no localhost SPA."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

TAB_NAMES: tuple[str, ...] = (
    "Dashboard",
    "Today",
    "Plan",
    "Bible",
    "Calendar",
    "Rules",
    "Schedules",
    "Device",
    "Watch",
    "Voice",
    "Settings",
)


class DesktopNavigator(QObject):
    """Emit tab name; MainWindow connects and switches stacked page."""

    tab_requested = Signal(str)

    def go(self, tab: str, *, show_window: bool = True) -> None:
        name = str(tab or "").strip()
        if name not in TAB_NAMES:
            return
        self.tab_requested.emit(name if show_window else f"::{name}")


_nav: DesktopNavigator | None = None


def navigator() -> DesktopNavigator:
    global _nav
    if _nav is None:
        _nav = DesktopNavigator()
    return _nav


def go_tab(tab: str, *, show_window: bool = True) -> None:
    navigator().go(tab, show_window=show_window)
