"""Qt dialogs for free-time PIN and hard-block notice (thread-safe via signals)."""

from __future__ import annotations

import webbrowser
from typing import Any

from PySide6.QtCore import QObject, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from backend.behavior.calt_desktop.constants import CALENDAR_URL

BIBLE_URL = "http://localhost:5173/bible"


class HardBlockBridge(QObject):
    """Marshal hard-block UI onto the Qt main thread."""

    show_requested = Signal(str, dict)

    def __init__(self) -> None:
        super().__init__()
        self._parent: QWidget | None = None
        self.show_requested.connect(self._on_show)

    def set_parent(self, parent: QWidget | None) -> None:
        self._parent = parent

    def request(self, *, exe: str, gate: dict[str, Any] | None) -> None:
        self.show_requested.emit(str(exe or ""), dict(gate or {}))

    @Slot(str, dict)
    def _on_show(self, exe: str, gate: dict) -> None:
        detail = str(gate.pop("_detail", "") or "")
        show_hard_block_dialog(self._parent, exe=exe, gate=gate, detail=detail)


_bridge: HardBlockBridge | None = None


def hard_block_bridge() -> HardBlockBridge:
    global _bridge
    if _bridge is None:
        _bridge = HardBlockBridge()
    return _bridge


def prompt_free_time(parent: QWidget | None = None) -> bool:
    """Ask for exit PIN / phrase, then set free override. Returns True if granted."""
    from backend.behavior.tracker_exit import (
        exit_confirmation_required,
        exit_secret_accepted,
    )

    if exit_confirmation_required():
        text, ok = QInputDialog.getText(
            parent,
            "Free time",
            "Enter TRACKER_EXIT_PIN:",
        )
        if not ok:
            return False
        if not exit_secret_accepted(text):
            QMessageBox.warning(parent, "Free time", "Incorrect PIN.")
            return False
    else:
        reply = QMessageBox.question(
            parent,
            "Free time",
            "Grant temporary free browse override?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return False

    from backend.behavior.browser_gate_policy import set_free_override

    set_free_override()
    QMessageBox.information(parent, "Free time", "Free browse override granted.")
    return True


def show_hard_block_dialog(
    parent: QWidget | None,
    *,
    exe: str = "",
    gate: dict[str, Any] | None = None,
    detail: str = "",
) -> None:
    """Richer hard-block card (progress + CTAs). Must run on Qt GUI thread."""
    g = gate or {}
    productive = int(g.get("productive_minutes") or 0)
    goal = int(g.get("daily_goal_minutes") or 240) or 240
    remaining = int(g.get("remaining_minutes") or max(0, goal - productive))
    pct = max(0, min(100, int(100 * productive / goal))) if goal else 0

    dlg = QDialog(parent)
    dlg.setWindowTitle("CALT — Hard block")
    dlg.setWindowModality(Qt.WindowModality.NonModal)
    dlg.setMinimumWidth(420)
    lay = QVBoxLayout(dlg)

    title = QLabel(f"Blocked: {exe or 'app'}")
    title.setStyleSheet("font-size: 16px; font-weight: 700;")
    lay.addWidget(title)

    focus = QLabel(f"Focus {productive} / {goal} min · {remaining} remaining")
    lay.addWidget(focus)
    if detail:
        dlab = QLabel(detail)
        dlab.setWordWrap(True)
        lay.addWidget(dlab)

    bar = QProgressBar()
    bar.setRange(0, 100)
    bar.setValue(pct)
    lay.addWidget(bar)

    tip = QLabel("Finish Bible + confirm plan, or Free time (PIN) if allowed.")
    tip.setWordWrap(True)
    tip.setStyleSheet("color: #94a3b8;")
    lay.addWidget(tip)

    row = QHBoxLayout()
    btn_bible = QPushButton("Open Bible")
    btn_bible.clicked.connect(lambda: webbrowser.open(BIBLE_URL))
    btn_cal = QPushButton("Open calendar")
    btn_cal.clicked.connect(lambda: webbrowser.open(CALENDAR_URL))
    btn_ok = QPushButton("OK")
    btn_ok.clicked.connect(dlg.accept)
    row.addWidget(btn_bible)
    row.addWidget(btn_cal)
    row.addStretch(1)
    row.addWidget(btn_ok)
    lay.addLayout(row)

    dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
    dlg.show()
    dlg.raise_()
    dlg.activateWindow()


def show_hard_block_notice(
    parent: QWidget | None,
    *,
    exe: str = "",
    detail: str = "",
    gate: dict[str, Any] | None = None,
) -> None:
    """Queue hard-block UI on the Qt main thread when Desktop is running."""
    payload = dict(gate or {})
    if detail:
        payload["_detail"] = detail
    try:
        from PySide6.QtWidgets import QApplication

        if QApplication.instance() is not None:
            hard_block_bridge().request(exe=exe, gate=payload)
            return
    except Exception:  # noqa: BLE001
        pass
    show_hard_block_dialog(parent, exe=exe, gate=payload, detail=detail)
