"""First-run banner when tracker has no linked user."""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton

from backend.behavior.calt_desktop.theme import primary_button
from backend.behavior.calt_desktop.widgets.gloss_panel import GlossPanel


class LinkAccountBanner(GlossPanel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("floatingDetail")
        row = QHBoxLayout()
        text = QLabel(
            "Account not linked — gate, planner, and SRS need a logged-in user. "
            "Open the web app, sign in, then restart the tracker if needed."
        )
        text.setWordWrap(True)
        row.addWidget(text, stretch=1)
        btn = primary_button("Open web app & sign in")
        btn.clicked.connect(self._open_web)
        row.addWidget(btn)
        self.body_layout().addLayout(row)

    def _open_web(self) -> None:
        try:
            from backend.behavior.stack_health import open_calt_page

            open_calt_page("/login", speak=False, auto_start=True)
        except Exception:  # noqa: BLE001
            pass

    def refresh(self, *, linked: bool) -> None:
        self.setVisible(not linked)
