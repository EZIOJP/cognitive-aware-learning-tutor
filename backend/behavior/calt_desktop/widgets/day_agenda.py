"""Day agenda — real planner blocks from SQLite (same DB as web API)."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from PySide6.QtCore import QTime, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from backend.behavior.calt_desktop.dialogs.planner_block import PlannerBlockDialog
from backend.behavior.calt_desktop.planner_data import (
    blocks_for_day,
    create_block,
    delete_block,
    update_block,
)
from backend.behavior.calt_desktop.theme import muted_label, primary_button
from backend.behavior.calt_desktop.widgets.block_list_table import BlockListTable
from backend.behavior.calt_desktop.widgets.gloss_panel import GlossPanel
from backend.behavior.calt_desktop.widgets.section_header import SectionHeader

if TYPE_CHECKING:
    from backend.behavior.tracker_service import TrackerService


class DayAgendaPanel(GlossPanel):
    """Editable list of planner blocks for one calendar day — DB-backed only."""

    blocks_changed = Signal()

    def __init__(self, service: TrackerService, *, day: date | None = None, parent=None) -> None:
        super().__init__(parent)
        self._service = service
        self._day = day or date.today()

        self.body_layout().addWidget(
            SectionHeader(
                "Today's plan blocks",
                "Loaded from vocab_app.db (PlannerBlock). Apply routines or Build to add rows.",
            )
        )

        self._day_label = QLabel("")
        self._day_label.setObjectName("muted")
        self.body_layout().addWidget(self._day_label)

        self._count = muted_label("")
        self.body_layout().addWidget(self._count)

        self._list = BlockListTable(
            empty_message="No blocks on this day yet. Step 1: Apply routines · Step 3: Build → Apply.",
            columns=("Time", "Title", "Category", "Status"),
        )
        self.body_layout().addWidget(self._list)

        row = QHBoxLayout()
        btn_add = primary_button("Add block")
        btn_add.clicked.connect(self._add_block)
        btn_edit = QPushButton("Edit")
        btn_edit.clicked.connect(self._edit_block)
        btn_del = QPushButton("Delete")
        btn_del.clicked.connect(self._delete_block)
        for b in (btn_add, btn_edit, btn_del):
            row.addWidget(b)
        row.addStretch(1)
        self.body_layout().addLayout(row)

    @property
    def day(self) -> date:
        return self._day

    def set_day(self, day: date) -> None:
        self._day = day
        self.reload()

    def reload(self) -> None:
        uid = int(getattr(self._service, "user_id", 0) or 0)
        self._day_label.setText(self._day.strftime("%A, %B %d, %Y"))
        if not uid:
            self._count.setText("Tracker user not linked — sign in once with API running.")
            self._list.set_blocks([], empty_message="Waiting for user_id from tracker…")
            return
        blocks = blocks_for_day(uid, self._day)
        total_min = sum(int(b.get("planned_minutes") or 0) for b in blocks)
        self._count.setText(
            f"{len(blocks)} block(s) · {total_min // 60}h {total_min % 60}m planned"
            if blocks
            else "0 blocks — complete Routines or Build steps above."
        )
        self._list.set_blocks(blocks)

    def _user_id(self) -> int:
        return int(getattr(self._service, "user_id", 0) or 0)

    def _add_block(self) -> None:
        uid = self._user_id()
        if not uid:
            QMessageBox.warning(self, "Plan", "No tracker user yet.")
            return
        dlg = PlannerBlockDialog(day=self._day, parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        v = dlg.values()
        if not v["title"]:
            QMessageBox.warning(self, "Plan", "Title is required.")
            return
        try:
            create_block(uid, day=self._day, **v)
            self.reload()
            self.blocks_changed.emit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Plan", str(exc))

    def _edit_block(self) -> None:
        uid = self._user_id()
        block = self._list.current_row_block()
        if not uid or not block:
            QMessageBox.information(self, "Plan", "Select a block to edit.")
            return
        start_parts = str(block.get("start_local") or "09:00").split(":")
        end_parts = str(block.get("end_local") or "10:00").split(":")
        dlg = PlannerBlockDialog(
            day=self._day,
            title=str(block.get("title") or ""),
            category=str(block.get("category") or "study"),
            start=QTime(int(start_parts[0]), int(start_parts[1])),
            end=QTime(int(end_parts[0]), int(end_parts[1])),
            parent=self,
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        v = dlg.values()
        try:
            update_block(
                uid,
                int(block["id"]),
                day=self._day,
                title=v["title"],
                category=v["category"],
                start_hour=v["start_hour"],
                start_minute=v["start_minute"],
                end_hour=v["end_hour"],
                end_minute=v["end_minute"],
            )
            self.reload()
            self.blocks_changed.emit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Plan", str(exc))

    def _delete_block(self) -> None:
        uid = self._user_id()
        block = self._list.current_row_block()
        if not uid or not block:
            QMessageBox.information(self, "Plan", "Select a block to delete.")
            return
        ans = QMessageBox.question(
            self,
            "Delete block",
            f"Delete “{block.get('title')}”?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ans != QMessageBox.StandardButton.Yes:
            return
        try:
            delete_block(uid, int(block["id"]))
            self.reload()
            self.blocks_changed.emit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Plan", str(exc))
