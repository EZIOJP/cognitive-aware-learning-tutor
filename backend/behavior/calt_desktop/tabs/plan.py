"""Plan tab — confirm morning plan; calendar edit stays on website."""

from __future__ import annotations

import webbrowser
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from backend.behavior.calt_desktop.constants import CALENDAR_URL

if TYPE_CHECKING:
    from backend.behavior.tracker_service import TrackerService


class PlanTab(QWidget):
    def __init__(self, service: TrackerService) -> None:
        super().__init__()
        self._service = service
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Confirm today's plan"))
        self._status = QLabel("…")
        self._status.setWordWrap(True)
        lay.addWidget(self._status)
        self._goals = QLineEdit()
        self._goals.setPlaceholderText("Today's goals (required to confirm)")
        lay.addWidget(self._goals)
        btn_confirm = QPushButton("Confirm plan")
        btn_confirm.clicked.connect(self.confirm)
        lay.addWidget(btn_confirm)
        btn_cal = QPushButton("Edit calendar in browser")
        btn_cal.clicked.connect(lambda: webbrowser.open(CALENDAR_URL))
        lay.addWidget(btn_cal)
        lay.addStretch(1)
        self.refresh()

    def refresh(self) -> None:
        try:
            gate = self._service.latest_gate() or {}
            morning = gate.get("morning") or {}
            self._status.setText(
                f"Morning next: {morning.get('next')}\n"
                f"Plan confirmed: {morning.get('plan_confirmed') or morning.get('confirmed')}"
            )
        except Exception as exc:  # noqa: BLE001
            self._status.setText(str(exc))

    def confirm(self) -> None:
        uid = int(getattr(self._service, "user_id", 0) or 0)
        goals = (self._goals.text() or "").strip()
        if not uid:
            QMessageBox.warning(self, "Plan", "No tracker user yet.")
            return
        if len(goals) < 3:
            QMessageBox.warning(self, "Plan", "Enter goals (at least 3 characters).")
            return
        try:
            from backend.bible import store as bible_store
            from backend.planner import morning_plan as morning_store
            from backend.planner import morning_rewards as morning_rewards_store

            bible = bible_store.summary(uid)
            chapter_goal = bible.get("chapter_goal") or {}
            chapters = list(bible.get("chapters_completed_today") or [])
            bible_done = bool(chapter_goal.get("met")) or len(chapters) >= 1
            if not bible_done:
                QMessageBox.warning(
                    self,
                    "Plan",
                    "Finish today's Bible chapter first (Bible tab / web reader).",
                )
                return
            try:
                morning_rewards_store.maybe_grant_bible(uid)
            except Exception:  # noqa: BLE001
                pass
            rewards = morning_rewards_store.summary(uid)
            bible_award = (rewards.get("awards") or {}).get("bible") or {}
            bible_completed_at = (
                bible_award.get("granted_at") if bible_award.get("granted") else None
            )
            morning_store.confirm_plan_today(
                uid,
                bible_done=True,
                bible_completed_at=bible_completed_at,
                goals=goals,
                require_goals=True,
            )
            try:
                self._service.latest_gate(force=True)
            except Exception:  # noqa: BLE001
                pass
            self.refresh()
            QMessageBox.information(self, "Plan", "Plan confirmed for today.")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Plan", str(exc))
