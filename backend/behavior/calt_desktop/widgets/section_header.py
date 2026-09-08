"""Explicit section title + description for Plan phase and Settings."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from backend.behavior.calt_desktop.theme import muted_label


class SectionHeader(QWidget):
    def __init__(
        self,
        title: str,
        description: str = "",
        *,
        badge: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        row = QLabel(title if not badge else f"{title}  ·  {badge}")
        row.setObjectName("sectionTitle")
        lay.addWidget(row)
        if description:
            lay.addWidget(muted_label(description))


class PhaseBanner(QWidget):
    """Top-of-tab label for Plan phase vs Settings."""

    def __init__(self, phase: str, subtitle: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 6)
        lay.setSpacing(2)
        title = QLabel(phase)
        title.setObjectName("hero")
        lay.addWidget(title)
        if subtitle:
            lay.addWidget(muted_label(subtitle))
