"""Qt dialogs for free-time PIN and hard-block notice (thread-safe via signals)."""

from __future__ import annotations

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

from backend.behavior.calt_desktop.navigation import go_tab


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
    from backend.behavior.break_reward import IncubationBlocksFreeOverride

    try:
        set_free_override()
    except IncubationBlocksFreeOverride as exc:
        QMessageBox.warning(parent, "Free time", str(exc))
        return False
    QMessageBox.information(parent, "Free time", "Free browse override granted.")
    return True


def prompt_spend_earned(parent: QWidget | None = None, *, user_id: int = 0) -> bool:
    """Q5 E1 — PIN → spend ledger minutes → set_free_override. Returns True on success."""
    from backend.behavior.break_reward import (
        IncubationBlocksFreeOverride,
        balance,
        spend,
    )
    from backend.behavior.tracker_exit import (
        exit_confirmation_required,
        exit_secret_accepted,
    )
    from backend.core.auth import ensure_solo_owner
    from backend.db.base import SessionLocal

    uid = int(user_id or 0)
    if uid <= 0:
        try:
            with SessionLocal() as db:
                uid = int(ensure_solo_owner(db).id)
        except Exception:
            QMessageBox.warning(parent, "Spend earned", "Could not resolve user.")
            return False

    try:
        bal = int(balance(uid))
    except Exception as exc:
        QMessageBox.warning(parent, "Spend earned", f"Ledger unavailable: {exc}")
        return False
    if bal <= 0:
        QMessageBox.information(parent, "Spend earned", "No earned free minutes yet.")
        return False

    mins, ok = QInputDialog.getInt(
        parent,
        "Spend earned",
        f"Spend how many earned minutes? (balance {bal})",
        bal,
        1,
        bal,
        1,
    )
    if not ok or mins <= 0:
        return False

    if exit_confirmation_required():
        text, pin_ok = QInputDialog.getText(
            parent,
            "Spend earned",
            "Enter TRACKER_EXIT_PIN:",
        )
        if not pin_ok:
            return False
        if not exit_secret_accepted(text):
            QMessageBox.warning(parent, "Spend earned", "Incorrect PIN.")
            return False
    else:
        reply = QMessageBox.question(
            parent,
            "Spend earned",
            f"Spend {mins} earned minute(s) for free browse?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return False

    try:
        result = spend(uid, int(mins), apply_override=True)
    except IncubationBlocksFreeOverride as exc:
        QMessageBox.warning(parent, "Spend earned", str(exc))
        return False
    except ValueError as exc:
        QMessageBox.warning(parent, "Spend earned", str(exc))
        return False
    except Exception as exc:
        QMessageBox.warning(parent, "Spend earned", f"Spend failed: {exc}")
        return False

    QMessageBox.information(
        parent,
        "Spend earned",
        f"Spent {result.get('spent', mins)} min — free browse granted "
        f"(balance {result.get('balance', 0)}).",
    )
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

    tip = QLabel(
        "Finish Bible + confirm plan in CALT Desktop · Focus, "
        "or Free time / Spend earned (PIN) if allowed. "
        "Incubation breaks cannot be skipped."
    )
    tip.setWordWrap(True)
    tip.setStyleSheet("color: #94a3b8;")
    lay.addWidget(tip)

    row = QHBoxLayout()
    btn_bible = QPushButton("Open Bible tab")
    btn_bible.clicked.connect(lambda: (go_tab("Bible"), dlg.accept()))
    btn_plan = QPushButton("Open Plan tab")
    btn_plan.clicked.connect(lambda: (go_tab("Plan"), dlg.accept()))
    btn_ok = QPushButton("OK")
    btn_ok.clicked.connect(dlg.accept)
    row.addWidget(btn_bible)
    row.addWidget(btn_plan)
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
