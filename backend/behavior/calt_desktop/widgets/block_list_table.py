"""Read-only block list — real DB or draft rows, never fake placeholder rows."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from PySide6.QtWidgets import (
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from backend.behavior.calt_desktop.theme import muted_label


def _fmt_local(iso: str | None) -> str:
    if not iso:
        return "—"
    raw = str(iso).replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return "—"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone().strftime("%H:%M")


def _time_range(block: dict[str, Any]) -> str:
    if block.get("start_local") and block.get("end_local"):
        return f"{block['start_local']}–{block['end_local']}"
    return f"{_fmt_local(block.get('start_at'))}–{_fmt_local(block.get('end_at'))}"


class BlockListTable(QWidget):
    """Shows real blocks or an empty-state label — no dummy table rows."""

    def __init__(
        self,
        *,
        empty_message: str = "No blocks yet.",
        columns: tuple[str, ...] = ("Time", "Title", "Category", "Status"),
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self._empty = muted_label(empty_message)
        self._empty.setWordWrap(True)
        self._table = QTableWidget(0, len(columns))
        self._table.setHorizontalHeaderLabels(list(columns))
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        lay.addWidget(self._empty)
        lay.addWidget(self._table)
        self._blocks: list[dict[str, Any]] = []

    def blocks(self) -> list[dict[str, Any]]:
        return list(self._blocks)

    def set_blocks(
        self,
        blocks: list[dict[str, Any]],
        *,
        empty_message: str | None = None,
        status_col: str = "status",
    ) -> None:
        if empty_message:
            self._empty.setText(empty_message)
        self._blocks = list(blocks or [])
        from backend.planner.morning_order import sort_blocks_chronological

        self._blocks = sort_blocks_chronological(self._blocks)
        self._table.setRowCount(0)
        if not self._blocks:
            self._empty.show()
            self._table.hide()
            return
        self._empty.hide()
        self._table.show()
        self._table.setRowCount(len(self._blocks))
        for row, b in enumerate(self._blocks):
            self._table.setItem(row, 0, QTableWidgetItem(_time_range(b)))
            self._table.setItem(row, 1, QTableWidgetItem(str(b.get("title") or "")))
            self._table.setItem(row, 2, QTableWidgetItem(str(b.get("category") or "")))
            if self._table.columnCount() > 3:
                status = str(b.get(status_col) or b.get("source") or "")
                self._table.setItem(row, 3, QTableWidgetItem(status))

    def current_row_block(self) -> dict[str, Any] | None:
        row = self._table.currentRow()
        if 0 <= row < len(self._blocks):
            return self._blocks[row]
        return None

    def table(self) -> QTableWidget:
        return self._table
