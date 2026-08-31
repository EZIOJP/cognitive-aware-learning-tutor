"""Qt dialogs for free-time PIN and hard-block notice."""

from __future__ import annotations

from PySide6.QtWidgets import QInputDialog, QMessageBox, QWidget


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


def show_hard_block_notice(
    parent: QWidget | None,
    *,
    exe: str = "",
    detail: str = "",
) -> None:
    QMessageBox.information(
        parent,
        "Hard block",
        f"Blocked: {exe or 'app'}\n{detail}\n\n"
        "Open Bible / Plan tabs, or use Free time if allowed.",
    )
