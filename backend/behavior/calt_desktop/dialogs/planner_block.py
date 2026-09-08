"""Add / edit planner block dialog."""

from __future__ import annotations

from datetime import date, datetime

from PySide6.QtCore import QTime
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QTimeEdit,
    QVBoxLayout,
)

BLOCK_CATEGORIES = [
    "Coding Practice",
    "AI / ML",
    "Study / Reading",
    "Coursework (Browser)",
    "personal",
    "break",
    "reading",
    "study",
    "lecture",
    "review",
]


class PlannerBlockDialog(QDialog):
    def __init__(
        self,
        *,
        day: date,
        title: str = "",
        category: str = "study",
        start: QTime | None = None,
        end: QTime | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Planner block")
        self._day = day

        lay = QVBoxLayout(self)
        form = QFormLayout()

        self._title = QLineEdit(title)
        form.addRow("Title", self._title)

        self._category = QComboBox()
        for c in BLOCK_CATEGORIES:
            self._category.addItem(c)
        idx = self._category.findText(category)
        self._category.setCurrentIndex(max(0, idx))
        form.addRow("Category", self._category)

        now = datetime.now()
        default_start = start or QTime(now.hour + 1 if now.minute else now.hour, 0)
        default_end = end or QTime(default_start.hour() + 1, default_start.minute())

        self._start = QTimeEdit(default_start)
        self._start.setDisplayFormat("HH:mm")
        form.addRow("Start", self._start)

        self._end = QTimeEdit(default_end)
        self._end.setDisplayFormat("HH:mm")
        form.addRow("End", self._end)

        lay.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

    @property
    def day(self) -> date:
        return self._day

    def values(self) -> dict:
        return {
            "title": self._title.text().strip(),
            "category": self._category.currentText(),
            "start_hour": self._start.time().hour(),
            "start_minute": self._start.time().minute(),
            "end_hour": self._end.time().hour(),
            "end_minute": self._end.time().minute(),
        }
