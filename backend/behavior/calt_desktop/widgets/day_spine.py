"""Today spine — vertical timeline of today's blocks."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from backend.behavior.calt_desktop.devotion_sync import devotion_status_for_spine, mark_devotion_for_block
from backend.behavior.calt_desktop.day_coach import spine_blocks
from backend.behavior.calt_desktop.navigation import go_tab
from backend.behavior.calt_desktop.theme import muted_label, primary_button
from backend.behavior.calt_desktop.widgets.gloss_panel import GlossPanel
from backend.behavior.calt_desktop.widgets.section_header import SectionHeader

if TYPE_CHECKING:
    from backend.behavior.tracker_service import TrackerService

_STATE_MARK = {"done": "✓", "active": "▶", "pending": "○"}


class DaySpinePanel(GlossPanel):
    block_action = Signal(str)

    def __init__(self, service: TrackerService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._service = service
        self.body_layout().addWidget(
            SectionHeader(
                "Today's spine",
                "Wake → Bible → bath → eat → study → sleep. Tap a row for actions.",
            )
        )
        self._summary = muted_label("")
        self.body_layout().addWidget(self._summary)

        self._list = QListWidget()
        self._list.setMaximumHeight(220)
        self._list.itemDoubleClicked.connect(self._on_item)
        self.body_layout().addWidget(self._list)

        row = QHBoxLayout()
        btn_plan = QPushButton("Open Plan")
        btn_plan.clicked.connect(lambda: go_tab("Plan"))
        btn_apply = primary_button("Apply my day")
        btn_apply.clicked.connect(lambda: self.block_action.emit("apply_day"))
        row.addWidget(btn_plan)
        row.addWidget(btn_apply)
        row.addStretch(1)
        self.body_layout().addLayout(row)

    def _uid(self) -> int:
        return int(getattr(self._service, "user_id", 0) or 0)

    def refresh(self) -> None:
        uid = self._uid()
        self._list.clear()
        if not uid:
            self._summary.setText("Sign in via web to load today's spine.")
            return
        blocks = spine_blocks(uid)
        devotion = devotion_status_for_spine(uid)
        done_n = sum(1 for b in blocks if b.get("spine_state") == "done")
        active = next((b for b in blocks if b.get("spine_state") == "active"), None)
        self._summary.setText(
            f"{len(blocks)} blocks · {done_n} done · "
            f"devotion M/A/E: {'✓' if devotion.get('morning') else '○'}/"
            f"{'✓' if devotion.get('afternoon') else '○'}/"
            f"{'✓' if devotion.get('evening') else '○'}"
            + (f" · Now: {active.get('title')}" if active else "")
        )
        for b in blocks:
            mark = _STATE_MARK.get(str(b.get("spine_state")), "○")
            line = (
                f"{mark} {b.get('start_local', '?')}–{b.get('end_local', '?')}  "
                f"{b.get('title', 'Block')}"
            )
            item = QListWidgetItem(line)
            item.setData(Qt.ItemDataRole.UserRole, b)
            if b.get("spine_state") == "active":
                item.setForeground(Qt.GlobalColor.cyan)
            self._list.addItem(item)

    def _on_item(self, item: QListWidgetItem) -> None:
        block = item.data(Qt.ItemDataRole.UserRole) or {}
        if not isinstance(block, dict):
            return
        cat = str(block.get("category") or "").lower()
        title = str(block.get("title") or "").lower()
        if cat == "spiritual" or "bible" in title:
            mark_devotion_for_block(self._uid(), block)
            go_tab("Bible")
        elif cat == "study" or "scaler" in title:
            go_tab("Plan")
        else:
            go_tab("Calendar")
