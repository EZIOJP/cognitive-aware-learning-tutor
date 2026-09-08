"""In-window floating detail card (not a separate OS dialog)."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from backend.behavior.calt_desktop.widgets.gloss_panel import GlossPanel


class FloatingDetailCard(GlossPanel):
    """Gloss panel overlay shown inside a tab; dismiss with × or Close."""

    closed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("floatingDetail")
        head = QHBoxLayout()
        self._title = QLabel("")
        self._title.setObjectName("sectionTitle")
        head.addWidget(self._title, stretch=1)
        btn_x = QPushButton("×")
        btn_x.setFixedSize(28, 28)
        btn_x.setObjectName("navChip")
        btn_x.clicked.connect(self.dismiss)
        head.addWidget(btn_x)
        self.body_layout().addLayout(head)

        self._content_host = QWidget()
        self._content_lay = QVBoxLayout(self._content_host)
        self._content_lay.setContentsMargins(0, 0, 0, 0)
        self._content_lay.setSpacing(8)
        self.body_layout().addWidget(self._content_host)
        self.hide()

    def set_title(self, text: str) -> None:
        self._title.setText(str(text or "").strip())

    def clear_content(self) -> None:
        while self._content_lay.count():
            item = self._content_lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def add_content(self, widget: QWidget) -> None:
        self._content_lay.addWidget(widget)

    def dismiss(self) -> None:
        self.hide()
        self.closed.emit()

    def show_card(self, title: str, body: QWidget) -> None:
        self.set_title(title)
        self.clear_content()
        self.add_content(body)
        self.show()
        self.raise_()
