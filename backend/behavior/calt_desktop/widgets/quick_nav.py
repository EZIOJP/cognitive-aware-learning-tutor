"""Compact in-app navigation chips (replaces web deep-links)."""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget

from backend.behavior.calt_desktop.navigation import go_tab


class QuickNavBar(QWidget):
    def __init__(
        self,
        tabs: tuple[str, ...] = ("Today", "Bible", "Plan", "Calendar"),
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        for name in tabs:
            btn = QPushButton(name)
            btn.setObjectName("navChip")
            btn.clicked.connect(lambda _c, t=name: go_tab(t))
            row.addWidget(btn)
        row.addStretch(1)
