"""Framed panel matching web gloss-panel styling."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QVBoxLayout, QWidget


class GlossPanel(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("glossPanel")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(14, 12, 14, 12)
        self._layout.setSpacing(10)

    def body_layout(self) -> QVBoxLayout:
        return self._layout
