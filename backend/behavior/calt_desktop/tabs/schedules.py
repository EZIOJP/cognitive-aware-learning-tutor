"""Schedules tab — Freedom-style gate windows (web-parity UI)."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from backend.behavior.calt_desktop.theme import muted_label, primary_button
from backend.behavior.calt_desktop.widgets.gloss_panel import GlossPanel

DAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


class _WindowEditor(GlossPanel):
    def __init__(self, data: dict[str, Any]) -> None:
        super().__init__()
        self._data = dict(data)
        form = QFormLayout()
        self._label = QLineEdit(str(data.get("label") or ""))
        form.addRow("Label", self._label)

        times = QHBoxLayout()
        self._start = QLineEdit(str(data.get("start") or "09:00"))
        self._start.setPlaceholderText("HH:MM")
        self._end = QLineEdit(str(data.get("end") or "18:00"))
        self._end.setPlaceholderText("HH:MM")
        times.addWidget(QLabel("Start"))
        times.addWidget(self._start)
        times.addWidget(QLabel("End"))
        times.addWidget(self._end)
        form.addRow("Window", times)

        self._mode = QComboBox()
        for m in ("study", "free", "planning"):
            self._mode.addItem(m, m)
        idx = self._mode.findData(str(data.get("mode") or "study"))
        self._mode.setCurrentIndex(max(0, idx))
        form.addRow("Mode", self._mode)

        self.body_layout().addLayout(form)

        self._day_checks: list[QCheckBox] = []
        days_row = QHBoxLayout()
        selected = set(int(d) for d in (data.get("days") or []) if isinstance(d, int))
        for i, name in enumerate(DAY_LABELS):
            cb = QCheckBox(name)
            cb.setChecked(i in selected)
            self._day_checks.append(cb)
            days_row.addWidget(cb)
        days_row.addStretch(1)
        self.body_layout().addLayout(days_row)

    def to_dict(self) -> dict[str, Any]:
        days = [i for i, cb in enumerate(self._day_checks) if cb.isChecked()]
        return {
            "id": str(self._data.get("id") or f"win-{id(self)}"),
            "label": self._label.text().strip() or "Window",
            "start": self._start.text().strip() or "09:00",
            "end": self._end.text().strip() or "18:00",
            "mode": str(self._mode.currentData() or "study"),
            "days": sorted(days),
        }


class SchedulesTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._loaded = False
        outer = QVBoxLayout(self)

        head = QHBoxLayout()
        title = QLabel("Recurring gate schedules")
        title.setObjectName("sectionTitle")
        head.addWidget(title)
        head.addStretch(1)
        self._btn_save = primary_button("Save")
        self._btn_save.clicked.connect(self.save)
        head.addWidget(self._btn_save)
        outer.addLayout(head)

        outer.addWidget(
            muted_label(
                "Freedom-style windows — force study, free, or planning browser mode by time of day."
            )
        )

        self._enabled = QCheckBox("Enable recurring schedules")
        outer.addWidget(self._enabled)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._scroll_body = QWidget()
        self._editors_lay = QVBoxLayout(self._scroll_body)
        self._editors_lay.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self._scroll_body)
        outer.addWidget(scroll, stretch=1)

        foot = QHBoxLayout()
        btn_reload = QPushButton("Reload")
        btn_reload.clicked.connect(self.reload)
        foot.addWidget(btn_reload)
        foot.addStretch(1)
        self._status = muted_label("")
        foot.addWidget(self._status)
        outer.addLayout(foot)

        self._editors: list[_WindowEditor] = []

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if not self._loaded:
            self._loaded = True
            self.reload()

    def _clear_editors(self) -> None:
        for ed in self._editors:
            ed.setParent(None)
            ed.deleteLater()
        self._editors.clear()

    def reload(self) -> None:
        from backend.behavior.gate_schedules import load_gate_schedules

        data = load_gate_schedules()
        self._enabled.setChecked(bool(data.get("enabled")))
        self._clear_editors()
        for win in data.get("windows") or []:
            if isinstance(win, dict):
                ed = _WindowEditor(win)
                self._editors.append(ed)
                self._editors_lay.addWidget(ed)
        self._status.setText("Loaded.")

    def save(self) -> None:
        from backend.behavior.gate_schedules import save_gate_schedules

        try:
            payload = {
                "enabled": self._enabled.isChecked(),
                "windows": [ed.to_dict() for ed in self._editors],
            }
            save_gate_schedules(payload)
            self._status.setText("Saved.")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Schedules", str(exc))
