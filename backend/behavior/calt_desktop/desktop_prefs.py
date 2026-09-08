"""Desktop UI preferences (last tab, window geometry)."""

from __future__ import annotations

from PySide6.QtCore import QSettings

_ORG = "CALT"
_APP = "CaltDesktop"


def _settings() -> QSettings:
    return QSettings(_ORG, _APP)


def save_last_tab(tab_name: str) -> None:
    name = (tab_name or "").strip()
    if name:
        _settings().setValue("ui/last_tab", name)


def load_last_tab(default: str = "Today") -> str:
    raw = _settings().value("ui/last_tab", default)
    return str(raw or default)


def save_window_geometry(win) -> None:
    _settings().setValue("ui/geometry", win.saveGeometry())


def restore_window_geometry(win) -> None:
    geo = _settings().value("ui/geometry")
    if geo is not None:
        win.restoreGeometry(geo)


def save_sidebar_collapsed(collapsed: bool) -> None:
    _settings().setValue("ui/sidebar_collapsed", bool(collapsed))


def load_sidebar_collapsed() -> bool:
    raw = _settings().value("ui/sidebar_collapsed", False)
    return str(raw).lower() in ("1", "true", "yes")


def save_morning_ritual_dismissed() -> None:
    from datetime import date

    _settings().setValue("ui/morning_ritual_dismissed", date.today().isoformat())


def load_morning_ritual_dismissed() -> bool:
    from datetime import date

    raw = str(_settings().value("ui/morning_ritual_dismissed", "") or "")
    return raw == date.today().isoformat()


def save_wake_hm(hm: str) -> None:
    v = (hm or "06:00").strip()
    if v:
        _settings().setValue("planner/wake_hm", v)


def load_wake_hm(default: str = "06:00") -> str:
    raw = _settings().value("planner/wake_hm", default)
    return str(raw or default)
