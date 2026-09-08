"""Voice notes tab — list, download, open clips from CALT Voice watch."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from backend.behavior.calt_desktop.constants import HUB_HEALTH_URL
from backend.behavior.calt_desktop.sync_status import voice_sync_summary
from backend.behavior.calt_desktop.tabs.watch import lan_base_hint, probe_hub_health
from backend.behavior.calt_desktop.theme import muted_label, primary_button
from backend.behavior.calt_desktop.widgets.tab_lifecycle import VisiblePollMixin
from backend.behavior.voice_notes import NOTES_DIR


def notes_dir() -> Path:
    return NOTES_DIR


def _fmt_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    return f"{max(1, round(size / 1024))} KB"


def _fmt_clip_time(mtime: float) -> str:
    try:
        return datetime.fromtimestamp(mtime).strftime("%m-%d %H:%M")
    except (OSError, ValueError, OverflowError):
        return ""


class VoiceTab(VisiblePollMixin, QWidget):
    REFRESH_MS = 12_000

    def __init__(self) -> None:
        super().__init__()
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Voice notes (CALT Voice watch → this PC)"))
        lay.addWidget(
            muted_label(
                "Watch: clock screen → tap to record → swipe ← Files → tap clip to send. "
                "Phone relays chunks to hub :8765."
            )
        )
        self._hub = QLabel("Hub: …")
        self._hub.setWordWrap(True)
        lay.addWidget(self._hub)
        self._sync = QLabel("")
        self._sync.setWordWrap(True)
        lay.addWidget(self._sync)
        self._pending = muted_label("")
        lay.addWidget(self._pending)
        self._list = QListWidget()
        lay.addWidget(self._list)
        self._status = muted_label("")
        lay.addWidget(self._status)
        self._help = muted_label("")
        self._help.setWordWrap(True)
        lay.addWidget(self._help)

        row = QHBoxLayout()
        btn_refresh = QPushButton("Refresh")
        btn_refresh.clicked.connect(self.reload)
        btn_open = QPushButton("Open selected")
        btn_open.clicked.connect(self.open_selected)
        btn_dl = primary_button("Download selected")
        btn_dl.clicked.connect(self.download_selected)
        btn_dl_all = QPushButton("Download all…")
        btn_dl_all.clicked.connect(self.download_all)
        btn_folder = QPushButton("Open folder")
        btn_folder.clicked.connect(self.open_folder)
        for b in (btn_refresh, btn_open, btn_dl, btn_dl_all, btn_folder):
            row.addWidget(b)
        row.addStretch(1)
        lay.addLayout(row)

        self._init_visible_poll(refresh=self.reload)

    def reload(self) -> None:
        from backend.behavior.voice_notes import list_notes, list_pending_uploads

        probe = probe_hub_health(timeout=1.5)
        if probe.get("ok"):
            self._hub.setText(f"Hub OK · {HUB_HEALTH_URL} · phone Base URL → {lan_base_hint()}")
            self._hub.setStyleSheet("color: #34d399; font-weight: 600;")
        else:
            self._hub.setText(
                f"Hub down ({probe.get('error', '?')}) — voice uploads cannot finish. "
                "Run desktop tracker so :8765 is listening."
            )
            self._hub.setStyleSheet("color: #f87171; font-weight: 600;")

        voice_at, voice_detail = voice_sync_summary()
        self._sync.setText(f"Last upload: {voice_at} — {voice_detail}")

        pending = list_pending_uploads()
        if pending:
            lines = [
                f"{p.get('name') or '?'}: {p.get('received_count')}/{p.get('total_chunks')} chunks"
                for p in pending
            ]
            self._pending.setText(
                "Receiving from watch: " + "; ".join(lines[:3])
                + (" …" if len(lines) > 3 else "")
            )
            self._pending.setStyleSheet("color: #fbbf24;")
        else:
            self._pending.setText("")
            self._pending.setStyleSheet("")

        self._list.clear()
        rows = list_notes()
        for row in rows:
            name = str(row.get("name") or "")
            size = int(row.get("size") or 0)
            when = _fmt_clip_time(float(row.get("mtime") or 0))
            suffix = f"  ·  {when}" if when else ""
            item = QListWidgetItem(f"{name}  ·  {_fmt_size(size)}{suffix}")
            item.setData(Qt.ItemDataRole.UserRole, name)
            self._list.addItem(item)

        folder = notes_dir()
        self._status.setText(f"{len(rows)} clip(s) in {folder}")

        if not rows and not pending:
            self._help.setText(
                "No recordings yet. Checklist:\n"
                "1) Desktop tracker running (hub :8765 up — see status above)\n"
                "2) Phone Zepp → CALT Voice settings → Base URL = PC LAN IP (not localhost)\n"
                "3) Watch → record → Files → tap clip until “Stored on …”\n"
                "4) Refresh this tab — pending chunks appear while transfer is in flight"
            )
        elif not rows and pending:
            self._help.setText(
                "Upload in progress — keep phone near watch until all chunks finish."
            )
        else:
            self._help.setText("")

    def _selected_name(self) -> str | None:
        item = self._list.currentItem()
        if not item:
            return None
        name = item.data(Qt.ItemDataRole.UserRole)
        return str(name) if name else None

    def download_selected(self) -> None:
        name = self._selected_name()
        if not name:
            QMessageBox.information(self, "Voice", "Select a clip first.")
            return
        try:
            from backend.behavior.voice_notes import resolve_note_path

            src = resolve_note_path(name)
            default = str(Path.home() / "Downloads" / name)
            dest, _ = QFileDialog.getSaveFileName(
                self,
                "Download voice recording",
                default,
                "Opus audio (*.opus)",
            )
            if not dest:
                return
            shutil.copy2(src, dest)
            QMessageBox.information(self, "Voice", f"Saved to\n{dest}")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Voice", str(exc))

    def download_all(self) -> None:
        from backend.behavior.voice_notes import list_notes, resolve_note_path

        rows = list_notes()
        if not rows:
            QMessageBox.information(self, "Voice", "No clips to download yet.")
            return
        folder = QFileDialog.getExistingDirectory(
            self,
            "Download all voice recordings",
            str(Path.home() / "Downloads"),
        )
        if not folder:
            return
        dest_dir = Path(folder)
        copied = 0
        for row in rows:
            name = str(row.get("name") or "")
            if not name:
                continue
            try:
                src = resolve_note_path(name)
                shutil.copy2(src, dest_dir / name)
                copied += 1
            except Exception:  # noqa: BLE001
                continue
        QMessageBox.information(self, "Voice", f"Copied {copied} file(s) to\n{dest_dir}")

    def open_selected(self) -> None:
        name = self._selected_name()
        if not name:
            QMessageBox.information(self, "Voice", "Select a clip first.")
            return
        try:
            from backend.behavior.voice_notes import resolve_note_path

            path = resolve_note_path(name)
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
