"""Schedules tab — enable/disable Freedom-style gate windows."""

from __future__ import annotations

import json

from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)


class SchedulesTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Gate schedules (JSON windows)"))
        self._enabled = QCheckBox("Schedules enabled")
        lay.addWidget(self._enabled)
        self._editor = QPlainTextEdit()
        self._editor.setPlaceholderText('{"windows":[...]}')
        lay.addWidget(self._editor)
        row = QHBoxLayout()
        btn_reload = QPushButton("Reload")
        btn_reload.clicked.connect(self.reload)
        btn_save = QPushButton("Save")
        btn_save.clicked.connect(self.save)
        row.addWidget(btn_reload)
        row.addWidget(btn_save)
        row.addStretch(1)
        lay.addLayout(row)
        self._status = QLabel("")
        lay.addWidget(self._status)
        self.reload()

    def reload(self) -> None:
        from backend.behavior.gate_schedules import load_gate_schedules

        data = load_gate_schedules()
        self._enabled.setChecked(bool(data.get("enabled")))
        self._editor.setPlainText(json.dumps({"windows": data.get("windows") or []}, indent=2))
        self._status.setText("Loaded.")

    def save(self) -> None:
        from backend.behavior.gate_schedules import save_gate_schedules

        try:
            raw = json.loads(self._editor.toPlainText() or "{}")
            if not isinstance(raw, dict):
                raise ValueError("Root must be an object")
            payload = {
                "enabled": self._enabled.isChecked(),
                "windows": raw.get("windows") if isinstance(raw.get("windows"), list) else [],
            }
            save_gate_schedules(payload)
            self._status.setText("Saved.")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Schedules", str(exc))
