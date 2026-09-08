"""Click block on 2D calendar → in-window floating card (not a separate dialog)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from backend.behavior.calt_desktop.dialogs.planner_block import PlannerBlockDialog
from backend.behavior.calt_desktop.planner_data import delete_block, update_block
from backend.behavior.calt_desktop.theme import muted_label


def _fmt_iso(iso: str | None) -> str:
    if not iso:
        return "—"
    raw = str(iso).replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return str(iso)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone().strftime("%H:%M")


def _fmt_range(block: dict[str, Any]) -> str:
    if block.get("start_local") and block.get("end_local"):
        return f"{block['start_local']} – {block['end_local']}"
    return f"{_fmt_iso(block.get('start_at'))} – {_fmt_iso(block.get('end_at'))}"


def build_plan_block_detail_widget(
    block: dict[str, Any],
    *,
    day: date,
    user_id: int,
    parent: QWidget | None = None,
    on_changed: Callable[[], None] | None = None,
    on_close: Callable[[], None] | None = None,
) -> QWidget:
    """Body for FloatingDetailCard — plan block details + edit/delete."""
    host = QWidget(parent)
    lay = QVBoxLayout(host)
    lay.setContentsMargins(0, 0, 0, 0)

    form = QFormLayout()
    form.addRow("Time", QLabel(_fmt_range(block)))
    form.addRow("Category", QLabel(str(block.get("category") or "—")))
    form.addRow("Status", QLabel(str(block.get("status") or "scheduled")))
    mins = int(block.get("planned_minutes") or 0)
    rem = block.get("remaining_minutes")
    form.addRow("Planned", QLabel(f"{mins // 60}h {mins % 60}m"))
    if rem is not None:
        rm = int(rem)
        form.addRow("Remaining", QLabel(f"{rm // 60}h {rm % 60}m"))
    lay.addLayout(form)
    lay.addWidget(muted_label("Edit opens a small form; calendar grid stays visible behind this card."))

    row = QHBoxLayout()
    btn_edit = QPushButton("Edit…")
    btn_del = QPushButton("Delete")
    btn_close = QPushButton("Close")

    def _edit() -> None:
        from PySide6.QtCore import QTime

        b = block
        sp = str(b.get("start_local") or "09:00").split(":")
        ep = str(b.get("end_local") or "10:00").split(":")
        dlg = PlannerBlockDialog(
            day=day,
            title=str(b.get("title") or ""),
            category=str(b.get("category") or "study"),
            start=QTime(int(sp[0]), int(sp[1])),
            end=QTime(int(ep[0]), int(ep[1])),
            parent=parent,
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        v = dlg.values()
        try:
            update_block(user_id, int(b["id"]), day=day, **v)
            if on_changed:
                on_changed()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(parent, "Edit block", str(exc))

    def _delete() -> None:
        if (
            QMessageBox.question(parent, "Delete", f"Delete “{block.get('title')}”?")
            != QMessageBox.StandardButton.Yes
        ):
            return
        try:
            delete_block(user_id, int(block["id"]))
            if on_changed:
                on_changed()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(parent, "Delete", str(exc))

    btn_edit.clicked.connect(_edit)
    btn_del.clicked.connect(_delete)
    if on_close:
        btn_close.clicked.connect(on_close)
    row.addWidget(btn_edit)
    row.addWidget(btn_del)
    row.addStretch(1)
    row.addWidget(btn_close)
    lay.addLayout(row)
    return host


def build_actual_segment_detail_widget(
    seg: dict[str, Any],
    *,
    hour: int,
    parent: QWidget | None = None,
) -> QWidget:
    host = QWidget(parent)
    lay = QVBoxLayout(host)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.addWidget(QLabel(str(seg.get("app_or_label") or seg.get("category") or "Activity")))
    form = QFormLayout()
    form.addRow("Hour row", QLabel(f"{hour:02d}:00"))
    sm = int(seg.get("start_min") or 0)
    em = int(seg.get("end_min") or sm + 5)
    form.addRow("Minutes in hour", QLabel(f"{sm}–{em} (of 0–60 axis)"))
    form.addRow("Category", QLabel(str(seg.get("category") or "—")))
    if seg.get("productivity_score") is not None:
        form.addRow("Score", QLabel(str(seg.get("productivity_score"))))
    lay.addLayout(form)
    lay.addWidget(muted_label("Tracked band — read-only (desktop tracker + watch)."))
    return host


class PlanBlockDetailDialog(QDialog):
    def __init__(
        self,
        block: dict[str, Any],
        *,
        day: date,
        user_id: int,
        parent: QWidget | None = None,
        on_changed=None,
    ) -> None:
        super().__init__(parent)
        self._block = block
        self._day = day
        self._user_id = user_id
        self._on_changed = on_changed
        self.setWindowTitle("Plan block")
        self.setMinimumWidth(360)

        lay = QVBoxLayout(self)
        title = QLabel(str(block.get("title") or "Untitled"))
        title.setObjectName("sectionTitle")
        title.setWordWrap(True)
        lay.addWidget(title)

        form = QFormLayout()
        form.addRow("Time", QLabel(_fmt_range(block)))
        form.addRow("Category", QLabel(str(block.get("category") or "—")))
        form.addRow("Status", QLabel(str(block.get("status") or "scheduled")))
        mins = int(block.get("planned_minutes") or 0)
        rem = block.get("remaining_minutes")
        form.addRow("Planned", QLabel(f"{mins // 60}h {mins % 60}m"))
        if rem is not None:
            rm = int(rem)
            form.addRow("Remaining", QLabel(f"{rm // 60}h {rm % 60}m"))
        form.addRow("Block ID", QLabel(str(block.get("id") or "—")))
        lay.addLayout(form)

        lay.addWidget(
            muted_label("Edit times in Plan tab or use Edit below. Calendar grid is read-only overlay.")
        )

        row = QDialogButtonBox()
        btn_edit = QPushButton("Edit…")
        btn_edit.clicked.connect(self._edit)
        btn_del = QPushButton("Delete")
        btn_del.clicked.connect(self._delete)
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        row.addButton(btn_edit, QDialogButtonBox.ButtonRole.ActionRole)
        row.addButton(btn_del, QDialogButtonBox.ButtonRole.DestructiveRole)
        row.addButton(btn_close, QDialogButtonBox.ButtonRole.RejectRole)
        lay.addWidget(row)

    def _edit(self) -> None:
        from PySide6.QtCore import QTime

        b = self._block
        sp = str(b.get("start_local") or "09:00").split(":")
        ep = str(b.get("end_local") or "10:00").split(":")
        dlg = PlannerBlockDialog(
            day=self._day,
            title=str(b.get("title") or ""),
            category=str(b.get("category") or "study"),
            start=QTime(int(sp[0]), int(sp[1])),
            end=QTime(int(ep[0]), int(ep[1])),
            parent=self,
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        v = dlg.values()
        try:
            update_block(
                self._user_id,
                int(b["id"]),
                day=self._day,
                **v,
            )
            if self._on_changed:
                self._on_changed()
            self.accept()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Edit block", str(exc))

    def _delete(self) -> None:
        if (
            QMessageBox.question(self, "Delete", f"Delete “{self._block.get('title')}”?")
            != QMessageBox.StandardButton.Yes
        ):
            return
        try:
            delete_block(self._user_id, int(self._block["id"]))
            if self._on_changed:
                self._on_changed()
            self.accept()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Delete", str(exc))


class ActualSegmentDetailDialog(QDialog):
    def __init__(self, seg: dict[str, Any], *, hour: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Tracked time")
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(str(seg.get("app_or_label") or seg.get("category") or "Activity")))
        form = QFormLayout()
        form.addRow("Hour row", QLabel(f"{hour:02d}:00"))
        sm = int(seg.get("start_min") or 0)
        em = int(seg.get("end_min") or sm + 5)
        form.addRow("Minutes in hour", QLabel(f"{sm}–{em} (of 0–60 axis)"))
        form.addRow("Category", QLabel(str(seg.get("category") or "—")))
        if seg.get("productivity_score") is not None:
            form.addRow("Score", QLabel(str(seg.get("productivity_score"))))
        lay.addLayout(form)
        lay.addWidget(muted_label("Actual band = desktop tracker + watch sleep clips (read-only)."))
        btn = QPushButton("Close")
        btn.clicked.connect(self.accept)
        lay.addWidget(btn)
