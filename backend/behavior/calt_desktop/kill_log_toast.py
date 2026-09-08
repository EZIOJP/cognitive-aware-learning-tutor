"""Watch enforcer_kills.log and toast via QSystemTrayIcon (maturity F4)."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QObject, QTimer
from PySide6.QtWidgets import QSystemTrayIcon

from backend.paths import ROOT

log = logging.getLogger("calt_desktop.kill_toast")

_KILL_LOG = ROOT / "data" / "behavior" / "enforcer_kills.log"


class KillLogToastWatcher(QObject):
    """Poll kill log; show tray notification for new lines."""

    def __init__(self, tray_icon: QSystemTrayIcon, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._tray = tray_icon
        self._pos = 0
        self._ready = False
        if _KILL_LOG.is_file():
            try:
                self._pos = _KILL_LOG.stat().st_size
            except OSError:
                self._pos = 0
        self._timer = QTimer(self)
        self._timer.setInterval(4000)
        self._timer.timeout.connect(self._tick)
        self._timer.start()
        # Skip toasting historical lines on first tick.
        QTimer.singleShot(1500, self._arm)

    def _arm(self) -> None:
        self._ready = True
        if _KILL_LOG.is_file():
            try:
                self._pos = _KILL_LOG.stat().st_size
            except OSError:
                pass

    def _tick(self) -> None:
        try:
            if not _KILL_LOG.is_file():
                return
            size = _KILL_LOG.stat().st_size
            if size < self._pos:
                self._pos = 0
            if size == self._pos:
                return
            with _KILL_LOG.open("r", encoding="utf-8", errors="replace") as f:
                f.seek(self._pos)
                chunk = f.read()
                self._pos = f.tell()
            if not self._ready or not chunk.strip():
                return
            lines = [ln.strip() for ln in chunk.splitlines() if ln.strip()]
            if not lines:
                return
            last = lines[-1]
            # "… kill pid=N exe=foo.exe"
            exe = last
            if "exe=" in last:
                exe = last.split("exe=", 1)[-1].strip() or last
            self._tray.showMessage(
                "CALT blocked an app",
                exe[:120],
                QSystemTrayIcon.MessageIcon.Warning,
                5000,
            )
        except Exception as exc:  # noqa: BLE001
            log.debug("kill toast: %s", exc)
