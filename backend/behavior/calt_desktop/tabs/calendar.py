"""Calendar tab — refined 2D day view (plan vs actual only)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from backend.behavior.calt_desktop.dialogs.block_detail import (
    build_actual_segment_detail_widget,
    build_plan_block_detail_widget,
)
from backend.behavior.calt_desktop.gate_summary import gate_lock_hint
from backend.behavior.calt_desktop.navigation import go_tab
from backend.behavior.calt_desktop.planner_api import fetch_actual_overlay
from backend.behavior.calt_desktop.planner_data import blocks_for_day
from backend.behavior.calt_desktop.planner_segments import plan_blocks_to_hour_segs
from backend.behavior.calt_desktop.theme import muted_label, primary_button
from backend.behavior.calt_desktop.widgets.day_grid_2d import DayGrid2DPanel
from backend.behavior.calt_desktop.widgets.floating_detail_card import FloatingDetailCard
from backend.behavior.calt_desktop.widgets.gloss_panel import GlossPanel
from backend.behavior.calt_desktop.widgets.tab_lifecycle import VisiblePollMixin

if TYPE_CHECKING:
    from backend.behavior.tracker_service import TrackerService


class CalendarTab(VisiblePollMixin, QWidget):
    REFRESH_MS = 30_000

    def __init__(self, service: TrackerService) -> None:
        super().__init__()
        self._service = service
        self._day = date.today()
        self._blocks: list[dict] = []
        self._open_block_id: int | None = None

        lay = QVBoxLayout(self)
        lay.setSpacing(10)

        top = QHBoxLayout()
        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        hero = QLabel("Calendar")
        hero.setObjectName("hero")
        title_col.addWidget(hero)
        title_col.addWidget(
            muted_label("Plan blocks vs what you actually did — click any bar for details.")
        )
        top.addLayout(title_col, stretch=1)

        self._day_label = QLabel("")
        self._day_label.setObjectName("sectionTitle")
        top.addWidget(self._day_label)

        btn_prev = QPushButton("←")
        btn_prev.setFixedWidth(36)
        btn_prev.clicked.connect(lambda: self._shift(-1))
        btn_today = QPushButton("Today")
        btn_today.clicked.connect(self._go_today)
        btn_next = QPushButton("→")
        btn_next.setFixedWidth(36)
        btn_next.clicked.connect(lambda: self._shift(1))
        for b in (btn_prev, btn_today, btn_next):
            top.addWidget(b)
        btn_refresh = QPushButton("Refresh")
        btn_refresh.clicked.connect(self.refresh)
        top.addWidget(btn_refresh)
        btn_plan = primary_button("Plan wizard")
        btn_plan.clicked.connect(lambda: go_tab("Plan"))
        top.addWidget(btn_plan)
        lay.addLayout(top)

        self._empty = muted_label("")
        self._empty.hide()
        lay.addWidget(self._empty)

        self._btn_plan_empty = primary_button("Open Plan wizard")
        self._btn_plan_empty.clicked.connect(lambda: go_tab("Plan"))
        self._btn_plan_empty.hide()
        lay.addWidget(self._btn_plan_empty)

        self._btn_bible_empty = QPushButton("Open Bible")
        self._btn_bible_empty.clicked.connect(lambda: go_tab("Bible"))
        self._btn_bible_empty.hide()
        lay.addWidget(self._btn_bible_empty)

        panel = GlossPanel()
        self._detail = FloatingDetailCard(panel)
        self._detail.closed.connect(self._detail.hide)
        panel.body_layout().addWidget(self._detail)
        self._grid = DayGrid2DPanel()
        self._grid.plan_block_clicked.connect(self._on_plan_click)
        self._grid.actual_segment_clicked.connect(self._on_actual_click)
        panel.body_layout().addWidget(self._grid)
        lay.addWidget(panel, stretch=1)

        self._status = muted_label("")
        lay.addWidget(self._status)

        self._init_visible_poll()

    def _uid(self) -> int:
        return int(getattr(self._service, "user_id", 0) or 0)

    def _on_plan_click(self, block: dict) -> None:
        uid = self._uid()
        if not uid:
            return
        bid = int(block.get("id") or 0)
        self._open_block_id = bid or None
        full = next((b for b in self._blocks if int(b.get("id") or 0) == bid), block)

        def _changed() -> None:
            self._reload_plan_data()

        body = build_plan_block_detail_widget(
            full,
            day=self._day,
            user_id=uid,
            parent=self,
            on_changed=_changed,
            on_close=self._detail.dismiss,
        )
        self._detail.show_card(str(full.get("title") or "Plan block"), body)

    def _on_actual_click(self, seg: dict, hour: int) -> None:
        body = build_actual_segment_detail_widget(seg, hour=hour, parent=self)
        title = str(seg.get("app_or_label") or seg.get("category") or "Tracked time")
        self._detail.show_card(title, body)

    def _shift(self, delta: int) -> None:
        self._day += timedelta(days=delta)
        self.refresh()

    def _go_today(self) -> None:
        self._day = date.today()
        self.refresh()

    def _reload_plan_data(self) -> None:
        """Refresh blocks + grid without tearing down the floating detail card."""
        uid = self._uid()
        if not uid:
            return
        self._blocks = blocks_for_day(uid, self._day)
        if self._open_block_id is not None:
            if not any(int(b.get("id") or 0) == self._open_block_id for b in self._blocks):
                self._detail.dismiss()
                self._open_block_id = None
        self._update_empty_state()
        self._apply_grid()

    def _update_empty_state(self) -> None:
        if not self._blocks:
            hint = ""
            try:
                gate = self._service.latest_gate() or {}
                hint = gate_lock_hint(gate)
            except Exception:  # noqa: BLE001
                pass
            base = "No plan blocks this day — use Plan wizard: Routines → Goals → Build → Apply."
            self._empty.setText(f"{base}\n{hint}" if hint else base)
            self._empty.show()
            self._btn_plan_empty.show()
            self._btn_bible_empty.show()
        else:
            self._empty.hide()
            self._btn_plan_empty.hide()
            self._btn_bible_empty.hide()

    def _apply_grid(self) -> None:
        plan_segs = plan_blocks_to_hour_segs(self._blocks, self._day)
        hour_slices: list = []
        overlay_err = ""
        try:
            overlay = fetch_actual_overlay(self._uid(), self._day)
            hour_slices = overlay.get("hour_slices") or []
        except Exception as exc:  # noqa: BLE001
            overlay_err = str(exc)
            hour_slices = []

        self._grid.set_data(self._day, plan_segs, hour_slices, blocks=self._blocks)
        lo, hi = self._grid.grid().visible_hour_range()
        total_min = sum(int(b.get("planned_minutes") or 0) for b in self._blocks)
        n_actual = sum(
            len(s.get("segments") or [])
            for s in hour_slices
            if isinstance(s, dict) and str(s.get("date") or "") == self._day.isoformat()
        )
        status = (
            f"Showing hours {lo:02d}:00–{hi:02d}:00 · "
            f"{len(self._blocks)} plan · {total_min // 60}h {total_min % 60}m scheduled · "
            f"{n_actual} tracked segment(s)"
        )
        if overlay_err:
            status += f" · overlay: {overlay_err}"
        self._status.setText(status)

    def refresh(self) -> None:
        uid = self._uid()
        self._day_label.setText(self._day.strftime("%a, %b %d"))

        if not uid:
            self._empty.setText("Waiting for tracker user…")
            self._empty.show()
            self._btn_plan_empty.hide()
            self._blocks = []
            self._grid.set_data(self._day, [], [])
            self._status.setText("")
            return

        self._blocks = blocks_for_day(uid, self._day)
        self._update_empty_state()
        self._apply_grid()
