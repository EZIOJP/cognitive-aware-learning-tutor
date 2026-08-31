"""Voice notes tab — list / open / reveal folder."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from backend.paths import ROOT


def notes_dir() -> Path:
    from backend.behavior.voice_notes import NOTES_DIR

    path = NOTES_DIR if NOTES_DIR.is_absolute() else ROOT / NOTES_DIR
    return path


class VoiceTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Voice notes (from CALT Voice watch)"))
        self._list = QListWidget()
        lay.addWidget(self._list)
        self._status = QLabel("")
        self._status.setStyleSheet("color: #94a3b8;")
        lay.addWidget(self._status)

        row = QHBoxLayout()
        btn_refresh = QPushButton("Refresh")
        btn_refresh.clicked.connect(self.reload)
        btn_open = QPushButton("Open selected")
        btn_open.clicked.connect(self.open_selected)
        btn_folder = QPushButton("Open folder")
        btn_folder.clicked.connect(self.open_folder)
        row.addWidget(btn_refresh)
        row.addWidget(btn_open)
        row.addWidget(btn_folder)
        row.addStretch(1)
        lay.addLayout(row)

        self._timer = QTimer(self)
        self._timer.setInterval(12_000)
        self._timer.timeout.connect(self.reload)
        self._timer.start()
        self.reload()

    def reload(self) -> None:
        from backend.behavior.voice_notes import list_notes

        self._list.clear()
        rows = list_notes()
        for row in rows:
            name = str(row.get("name") or "")
            size = int(row.get("size") or 0)
            kb = max(1, round(size / 1024))
            item = QListWidgetItem(f"{name}  ·  {kb} KB")
            item.setData(Qt.ItemDataRole.UserRole, name)
            self._list.addItem(item)
        self._status.setText(f"{len(rows)} clip(s) in {notes_dir()}")

    def _selected_name(self) -> str | None:
        item = self._list.currentItem()
        if not item:
            return None
        name = item.data(Qt.ItemDataRole.UserRole)
        return str(name) if name else None

    def open_selected(self) -> None:
        name = self._selected_name()
        if not name:
            QMessageBox.information(self, "Voice", "Select a clip first.")
            return
        try:
            from backend.behavior.voice_notes import resolve_note_path

            path = resolve_note_path(name)
            if not path.is_absolute():
                path = ROOT / path
            if sys.platform == "win32":
                os.startfile(str(path))  # noqa: S606
            else:
                subprocess.Popen(["xdg-open", str(path)])  # noqa: S603
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Voice", str(exc))

    def open_folder(self) -> None:
        path = notes_dir()
        path.mkdir(parents=True, exist_ok=True)
        try:
            if sys.platform == "win32":
                os.startfile(str(path))  # noqa: S606
            else:
                subprocess.Popen(["xdg-open", str(path)])  # noqa: S603
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Voice", str(exc))
