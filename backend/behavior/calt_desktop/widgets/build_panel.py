"""Build / propose step — draft preview + apply (same merge logic as web)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from backend.behavior.calt_desktop.planner_api import (
    apply_proposed_filtered,
    format_goals_for_prompt,
    load_goals,
    run_propose_merged,
)
from backend.behavior.calt_desktop.theme import muted_label, primary_button
from backend.behavior.calt_desktop.sleep_anchor import sleep_summary
from backend.planner.morning_order import morning_order_rule_text
from backend.behavior.calt_desktop.widgets.block_list_table import BlockListTable
from backend.behavior.calt_desktop.widgets.section_header import SectionHeader

_HORIZON = (
    ("day", "Today", 1),
    ("week", "This week", 7),
    ("month", "This month", 30),
    ("custom", "Custom", 0),
)


class BuildPanel(QWidget):
    applied = Signal()
    proposed_changed = Signal(list)

    def __init__(self, user_id: int = 0, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._user_id = user_id
        self._proposed: list[dict[str, Any]] = []
        self._meta: dict[str, Any] = {}

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(
            SectionHeader(
                "Build schedule",
                "Smart gap-fill or AI propose → preview draft below → Apply writes new blocks to DB.",
                badge="Step 3",
            )
        )

        hrow = QHBoxLayout()
        hrow.addWidget(QLabel("Horizon"))
        self._horizon = QComboBox()
        for _id, label, _days in _HORIZON:
            self._horizon.addItem(label, _id)
        self._horizon.setCurrentIndex(1)
        self._horizon.currentIndexChanged.connect(self._on_horizon)
        hrow.addWidget(self._horizon)
        self._custom_days = QSpinBox()
        self._custom_days.setRange(1, 31)
        self._custom_days.setValue(14)
        self._custom_days.hide()
        hrow.addWidget(self._custom_days)
        hrow.addStretch(1)
        lay.addLayout(hrow)

        brow = QHBoxLayout()
        btn_smart = QPushButton("Smart gap-fill")
        btn_smart.clicked.connect(lambda: self._run("smart", use_llm=False))
        btn_review = QPushButton("AI review")
        btn_review.clicked.connect(lambda: self._run("review", use_llm=True))
        btn_ai = primary_button("AI propose")
        btn_ai.clicked.connect(lambda: self._run("full", use_llm=True))
        for b in (btn_smart, btn_review, btn_ai):
            brow.addWidget(b)
        lay.addLayout(brow)

        self._status = muted_label(
            f"No draft yet — run Smart gap-fill. {morning_order_rule_text()} · {sleep_summary()}"
        )
        lay.addWidget(self._status)

        self._draft = BlockListTable(
            empty_message="Draft empty. Generate to see proposed blocks (existing calendar rows marked “existing”).",
            columns=("Time", "Title", "Category", "Source"),
        )
        lay.addWidget(self._draft)

        arow = QHBoxLayout()
        self._btn_apply_today = QPushButton("Apply today")
        self._btn_apply_today.clicked.connect(lambda: self._apply(scope="today"))
        self._btn_apply = primary_button("Apply horizon")
        self._btn_apply.clicked.connect(lambda: self._apply(scope="horizon"))
        self._btn_clear = QPushButton("Clear draft")
        self._btn_clear.clicked.connect(self._clear)
        for b in (self._btn_apply_today, self._btn_apply, self._btn_clear):
            arow.addWidget(b)
        arow.addStretch(1)
        lay.addLayout(arow)

    def set_user_id(self, user_id: int) -> None:
        self._user_id = user_id

    def horizon_days(self) -> int:
        key = self._horizon.currentData()
        if key == "day":
            return 1
        if key == "week":
            return 7
        if key == "month":
            return 30
        return int(self._custom_days.value())

    def has_draft(self) -> bool:
        return any(str(b.get("source") or "") != "existing" for b in self._proposed)

    def _on_horizon(self) -> None:
        self._custom_days.setVisible(self._horizon.currentData() == "custom")

    def _refresh_draft_table(self) -> None:
        self._draft.set_blocks(
            self._proposed,
            status_col="source",
            empty_message="Draft empty — generate blocks first.",
        )

    def _run(self, mode: str, *, use_llm: bool) -> None:
        uid = self._user_id
        if not uid:
            QMessageBox.warning(self, "Build", "No tracker user — start API and sign in once.")
            return
        goals = format_goals_for_prompt(load_goals())
        days = self.horizon_days()
        draft = None
        if mode == "review" and self._proposed:
            draft = [
                {
                    "title": b.get("title"),
                    "category": b.get("category"),
                    "start_at": b.get("start_at"),
                    "end_at": b.get("end_at"),
                    "source": b.get("source") or "study",
                }
                for b in self._proposed
                if str(b.get("source") or "") != "existing"
            ]
        self._status.setText("Building…")
        try:
            res = run_propose_merged(
                uid,
                goals=goals,
                horizon_days=days,
                use_llm=use_llm,
                mode=mode,
                draft_blocks=draft,
            )
            self._proposed = list(res.get("blocks") or [])
            self._meta = res
            new_count = sum(1 for b in self._proposed if str(b.get("source") or "") != "existing")
            existing_count = len(self._proposed) - new_count
            label = {"smart": "Smart", "review": "AI review", "full": "AI propose"}.get(mode, mode)
            self._status.setText(
                f"{label}: {new_count} new · {existing_count} already on calendar · "
                f"{'LLM' if res.get('used_llm') else 'rules'}"
            )
            self._refresh_draft_table()
            self.proposed_changed.emit(self._proposed)
        except Exception as exc:  # noqa: BLE001
            self._status.setText(f"Failed: {exc}")

    def _apply(self, *, scope: str) -> None:
        uid = self._user_id
        if not uid or not self._proposed:
            QMessageBox.information(self, "Build", "Generate a draft first.")
            return
        start = date.today()
        if scope == "today":
            end = start
        else:
            end = start + timedelta(days=max(1, self.horizon_days()) - 1)
        try:
            res = apply_proposed_filtered(uid, self._proposed, range_start=start, range_end=end)
            self._proposed = []
            self._meta = {}
            self._refresh_draft_table()
            self._status.setText(
                f"Applied {res.get('created', 0)} block(s) to DB "
                f"(skipped {res.get('skipped_overlaps', 0)} overlaps)"
            )
            self.proposed_changed.emit([])
            self.applied.emit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Build", str(exc))

    def _clear(self) -> None:
        self._proposed = []
        self._refresh_draft_table()
        self._status.setText("Draft cleared.")
        self.proposed_changed.emit([])
