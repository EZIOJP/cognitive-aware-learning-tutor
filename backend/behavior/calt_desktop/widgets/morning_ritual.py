"""Morning launch ritual — 60s flow on first open."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from backend.behavior.calt_desktop.desktop_prefs import load_morning_ritual_dismissed, save_morning_ritual_dismissed
from backend.behavior.calt_desktop.navigation import go_tab
from backend.behavior.calt_desktop.theme import muted_label, primary_button
from backend.behavior.calt_desktop.widgets.gloss_panel import GlossPanel

if TYPE_CHECKING:
    from backend.behavior.tracker_service import TrackerService


class MorningRitualPanel(GlossPanel):
    def __init__(self, service: TrackerService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._service = service
        self.setStyleSheet(
            "GlossPanel { border: 1px solid rgba(129,140,248,0.45); background: rgba(30,27,75,0.5); }"
        )
        title = QLabel("Morning ritual")
        title.setObjectName("sectionTitle")
        self.body_layout().addWidget(title)
        self._line = QLabel("")
        self._line.setWordWrap(True)
        self.body_layout().addWidget(self._line)
        self._detail = muted_label("")
        self.body_layout().addWidget(self._detail)

        row = QHBoxLayout()
        self._btn_bible = primary_button("1 · Bible")
        self._btn_bible.clicked.connect(lambda: go_tab("Bible"))
        self._btn_plan = QPushButton("2 · Plan")
        self._btn_plan.clicked.connect(lambda: go_tab("Plan"))
        self._btn_review = QPushButton("3 · Review due")
        self._btn_review.clicked.connect(self._open_review)
        self._btn_dismiss = QPushButton("Dismiss for today")
        self._btn_dismiss.clicked.connect(self._dismiss)
        for b in (self._btn_bible, self._btn_plan, self._btn_review, self._btn_dismiss):
            row.addWidget(b)
        row.addStretch(1)
        self.body_layout().addLayout(row)

    def should_show(self) -> bool:
        if load_morning_ritual_dismissed():
            return False
        try:
            from datetime import datetime

            if datetime.now().hour >= 12:
                return False
        except Exception:  # noqa: BLE001
            pass
        return True

    def refresh(self) -> None:
        uid = int(getattr(self._service, "user_id", 0) or 0)
        bible_ok = False
        due = 0
        gate_s = "—"
        if uid:
            try:
                from backend.bible import store as bible_store

                bible = bible_store.summary(uid)
                chapters = list(bible.get("chapters_completed_today") or [])
                goal = bible.get("chapter_goal") or {}
                bible_ok = bool(goal.get("met")) or len(chapters) >= 1
            except Exception:  # noqa: BLE001
                pass
            try:
                gate = self._service.latest_gate() or {}
                morning = gate.get("morning") or {}
                gate_s = str(morning.get("next") or "open")
            except Exception:  # noqa: BLE001
                pass
            try:
                from backend.db.base import SessionLocal
                from backend.quiz.review_cards import backlog_summary

                db = SessionLocal()
                try:
                    due = int(backlog_summary(db, user_id=uid).get("due_count") or 0)
                finally:
                    db.close()
            except Exception:  # noqa: BLE001
                due = 0

        self._line.setText(
            f"Bible {'✓' if bible_ok else '○'} · Gate next: {gate_s} · Review due: {due}"
        )
        self._detail.setText(
            "Lord's Prayer → Apply my day on Plan → confirm blocks. "
            "Dismiss hides this until tomorrow."
        )
        self.setVisible(self.should_show())

    def _dismiss(self) -> None:
        save_morning_ritual_dismissed()
        self.hide()

    def _open_review(self) -> None:
        try:
            from backend.behavior.stack_health import open_calt_page

            open_calt_page("/review", speak=False, auto_start=True)
        except Exception:  # noqa: BLE001
            go_tab("Plan")
