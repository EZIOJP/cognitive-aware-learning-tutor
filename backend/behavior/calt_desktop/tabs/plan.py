"""Plan tab — explicit PLAN PHASE layout, real DB blocks only."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from backend.behavior.calt_desktop.navigation import go_tab
from backend.behavior.calt_desktop.planner_api import (
    google_calendar_status,
    load_goals,
    revert_last_apply_api,
    sync_google_calendar,
)
from backend.behavior.calt_desktop.sleep_anchor import sleep_summary
from backend.behavior.calt_desktop.planner_data import blocks_for_day
from backend.behavior.calt_desktop.theme import muted_label, primary_button
from backend.behavior.calt_desktop.widgets.build_panel import BuildPanel
from backend.behavior.calt_desktop.widgets.day_agenda import DayAgendaPanel
from backend.behavior.calt_desktop.widgets.gloss_panel import GlossPanel
from backend.behavior.calt_desktop.widgets.goals_panel import GoalsPanel
from backend.behavior.calt_desktop.widgets.routines_panel import RoutinesPanel
from backend.behavior.calt_desktop.widgets.section_header import PhaseBanner, SectionHeader
from backend.behavior.calt_desktop.widgets.tab_lifecycle import VisiblePollMixin

if TYPE_CHECKING:
    from backend.behavior.tracker_service import TrackerService

_STEP_LABELS = ("1 Routines", "2 Goals", "3 Build", "4 Confirm", "5 Sync")
_STEP_DESCS = (
    "Seed/edit life blocks · Apply for today writes PlannerRoutine → PlannerBlock.",
    "Main goal + focus hours · saved to JSON + productivity policy in DB.",
    "Gap-fill or AI · preview draft · Apply creates new PlannerBlock rows.",
    "Review real blocks from DB · confirm morning plan (requires Bible done).",
    "Optional Google Calendar export · then open 2D Calendar tab.",
)


class PlanTab(VisiblePollMixin, QWidget):
    REFRESH_MS = 20_000

    def __init__(self, service: TrackerService) -> None:
        super().__init__()
        self._service = service
        self._step = 0
        self._goals_done = False
        self._applied = False
        self._step_buttons: list[QPushButton] = []

        outer = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        body = QWidget()
        lay = QVBoxLayout(body)
        scroll.setWidget(body)
        outer.addWidget(scroll)

        lay.addWidget(
            PhaseBanner(
                "Plan phase",
                "Morning planning wizard — same SQLite + backend logic as web /api/planner.",
            )
        )

        self._gate_banner = QLabel("")
        self._gate_banner.setWordWrap(True)
        self._gate_banner.setStyleSheet(
            "background: rgba(99,102,241,0.2); border:1px solid rgba(129,140,248,0.4);"
            " border-radius:10px; padding:10px; color:#e0e7ff;"
        )
        lay.addWidget(self._gate_banner)

        quick = QHBoxLayout()
        btn_apply_day = primary_button("Apply my day")
        btn_apply_day.clicked.connect(self._apply_my_day)
        btn_revert = QPushButton("Revert last apply")
        btn_revert.clicked.connect(self._revert_apply)
        self._apply_status = muted_label(sleep_summary())
        quick.addWidget(btn_apply_day)
        quick.addWidget(btn_revert)
        quick.addStretch(1)
        lay.addLayout(quick)
        lay.addWidget(self._apply_status)

        self._step_desc = muted_label(_STEP_DESCS[0])
        lay.addWidget(self._step_desc)

        rail = QHBoxLayout()
        for i, label in enumerate(_STEP_LABELS):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setObjectName("stepRail")
            btn.clicked.connect(lambda _c, idx=i: self._goto_step(idx))
            self._step_buttons.append(btn)
            rail.addWidget(btn)
        lay.addLayout(rail)

        self._stack = QStackedWidget()
        uid = self._uid()

        self._routines = RoutinesPanel(uid)
        self._routines.changed.connect(self._on_data_changed)
        self._stack.addWidget(self._wrap_step(self._routines))

        self._goals = GoalsPanel(uid)
        self._goals.saved.connect(self._on_goals_saved)
        self._stack.addWidget(self._wrap_step(self._goals))

        self._build = BuildPanel(uid)
        self._build.applied.connect(self._on_build_applied)
        self._stack.addWidget(self._wrap_step(self._build))

        confirm = QWidget()
        cv = QVBoxLayout(confirm)
        cv.addWidget(
            SectionHeader(
                "Confirm plan",
                "Only blocks already in vocab_app.db appear below — not draft placeholders.",
                badge="Step 4",
            )
        )
        self._agenda = DayAgendaPanel(service, day=date.today())
        self._agenda.blocks_changed.connect(self._on_data_changed)
        cv.addWidget(self._agenda)
        cv.addWidget(QLabel("Goals text for morning gate"))
        self._confirm_goals = QLineEdit()
        self._confirm_goals.setPlaceholderText("Same as main goal — min 3 characters")
        cv.addWidget(self._confirm_goals)
        btn_confirm = primary_button("Confirm plan for today")
        btn_confirm.clicked.connect(self.confirm)
        cv.addWidget(btn_confirm)
        self._stack.addWidget(self._wrap_step(confirm, margin_only=True))

        sync_w = QWidget()
        sv = QVBoxLayout(sync_w)
        sv.addWidget(
            SectionHeader(
                "Sync & calendar",
                "Optional Google export · view plan + actual on Calendar tab.",
                badge="Step 5",
            )
        )
        self._sync_status = muted_label("")
        sv.addWidget(self._sync_status)
        btn_sync = QPushButton("Sync next 14 days to Google")
        btn_sync.clicked.connect(self._sync_gcal)
        sv.addWidget(btn_sync)
        btn_cal = primary_button("Open 2D Calendar")
        btn_cal.clicked.connect(lambda: go_tab("Calendar"))
        sv.addWidget(btn_cal)
        self._stack.addWidget(self._wrap_step(sync_w, margin_only=True))

        lay.addWidget(self._stack)

        nav = QHBoxLayout()
        self._btn_back = QPushButton("← Back")
        self._btn_back.clicked.connect(lambda: self._goto_step(self._step - 1))
        self._btn_next = primary_button("Next →")
        self._btn_next.clicked.connect(lambda: self._goto_step(self._step + 1))
        nav.addWidget(self._btn_back)
        nav.addStretch(1)
        nav.addWidget(self._btn_next)
        lay.addLayout(nav)

        g = load_goals()
        if str(g.get("mainGoal") or "").strip():
            self._goals_done = True
        self._confirm_goals.setText(str(g.get("mainGoal") or "")[:200])
        self._goto_step(0)
        self._init_visible_poll()

    @staticmethod
    def _wrap_step(inner: QWidget, *, margin_only: bool = False) -> GlossPanel:
        panel = GlossPanel()
        if margin_only:
            panel.body_layout().addWidget(inner)
        else:
            panel.body_layout().addWidget(inner)
        return panel

    def _uid(self) -> int:
        return int(getattr(self._service, "user_id", 0) or 0)

    def _apply_my_day(self) -> None:
        uid = self._uid()
        if not uid:
            self._apply_status.setText("No user — sign in via web.")
            return
        try:
            from backend.behavior.calt_desktop.day_coach import apply_my_day

            res = apply_my_day(uid)
            if res.get("ok"):
                self._apply_status.setText(
                    f"Done: +{res.get('routines_created', 0)} routines, "
                    f"+{res.get('study_created', 0)} study · "
                    f"skipped {res.get('skipped_overlaps', 0)} overlaps"
                )
                self._applied = True
                self._routines.reload()
                self._agenda.reload()
                self._update_step_styles()
            else:
                self._apply_status.setText(str(res.get("error")))
        except Exception as exc:  # noqa: BLE001
            self._apply_status.setText(str(exc))

    def _revert_apply(self) -> None:
        uid = self._uid()
        if not uid:
            return
        try:
            res = revert_last_apply_api(uid)
            if res.get("ok"):
                self._apply_status.setText(
                    f"Reverted: removed {res.get('removed', 0)}, restored {res.get('restored', 0)}"
                )
                self._agenda.reload()
                self._routines.reload()
            else:
                self._apply_status.setText(str(res.get("error") or "Nothing to revert"))
        except Exception as exc:  # noqa: BLE001
            self._apply_status.setText(str(exc))
    def _on_goals_saved(self, data: dict) -> None:
        self._goals_done = True
        self._confirm_goals.setText(str(data.get("mainGoal") or "")[:200])
        self._update_step_styles()

    def _on_build_applied(self) -> None:
        self._applied = True
        self._agenda.reload()
        self._update_step_styles()
        self._goto_step(3)

    def _on_data_changed(self) -> None:
        self._update_step_styles()

    def _routines_done(self) -> bool:
        uid = self._uid()
        if not uid:
            return False
        return self._routines.has_routines() or bool(blocks_for_day(uid, date.today()))

    def _build_done(self) -> bool:
        return self._applied or self._build.has_draft()

    def _update_step_styles(self) -> None:
        done_flags = [
            self._routines_done(),
            self._goals_done,
            self._build_done(),
            False,
            False,
        ]
        for i, btn in enumerate(self._step_buttons):
            if done_flags[i]:
                btn.setStyleSheet("border-color: rgba(16,185,129,0.6); color: #a7f3d0;")
            else:
                btn.setStyleSheet("")

    def _goto_step(self, idx: int) -> None:
        idx = max(0, min(len(_STEP_LABELS) - 1, idx))
        self._step = idx
        self._stack.setCurrentIndex(idx)
        self._step_desc.setText(_STEP_DESCS[idx])
        for i, btn in enumerate(self._step_buttons):
            btn.setChecked(i == idx)
        self._btn_back.setEnabled(idx > 0)
        self._btn_next.setEnabled(idx < len(_STEP_LABELS) - 1)
        if idx == 3:
            self._agenda.reload()
        if idx == 4:
            self._refresh_sync_status()
        self._update_step_styles()

    def _refresh_sync_status(self) -> None:
        try:
            st = google_calendar_status()
            if st.get("configured") and st.get("connected"):
                self._sync_status.setText("Google Calendar connected.")
            elif st.get("configured"):
                self._sync_status.setText("OAuth configured — optional.")
            else:
                self._sync_status.setText("Google Calendar not configured (optional).")
        except Exception as exc:  # noqa: BLE001
            self._sync_status.setText(str(exc))

    def _sync_gcal(self) -> None:
        uid = self._uid()
        if not uid:
            return
        try:
            res = sync_google_calendar(uid)
            QMessageBox.information(self, "Sync", str(res))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Sync", str(exc))

    def refresh(self) -> None:
        uid = self._uid()
        self._routines.set_user_id(uid)
        self._goals.set_user_id(uid)
        self._build.set_user_id(uid)
        try:
            gate = self._service.latest_gate() or {}
            morning = gate.get("morning") or {}
            if str(morning.get("next") or "") == "plan":
                self._gate_banner.setText("Gate: planning required — complete steps 1–4.")
                self._gate_banner.show()
            else:
                self._gate_banner.hide()
        except Exception:  # noqa: BLE001
            self._gate_banner.hide()
        self._routines.reload()
        self._agenda.set_day(date.today())
        self._update_step_styles()

    def confirm(self) -> None:
        uid = self._uid()
        goals = (self._confirm_goals.text() or "").strip()
        if not uid:
            QMessageBox.warning(self, "Plan", "No tracker user yet.")
            return
        if len(goals) < 3:
            QMessageBox.warning(self, "Plan", "Enter goals (at least 3 characters).")
            return
        blocks = blocks_for_day(uid, date.today())
        if not blocks:
            QMessageBox.warning(
                self,
                "Plan",
                "No blocks in DB for today — Step 1 Apply routines or Step 3 Build → Apply.",
            )
            return
        try:
            from backend.bible import store as bible_store
            from backend.planner import morning_plan as morning_store
            from backend.planner import morning_rewards as morning_rewards_store

            bible = bible_store.summary(uid)
            chapters = list(bible.get("chapters_completed_today") or [])
            chapter_goal = bible.get("chapter_goal") or {}
            bible_done = bool(chapter_goal.get("met")) or len(chapters) >= 1
            if not bible_done:
                QMessageBox.warning(self, "Plan", "Finish Bible tab first.")
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
            self._service.latest_gate(force=True)
            QMessageBox.information(
                self,
                "Plan",
                f"Confirmed with {len(blocks)} block(s) on today's calendar.",
            )
            self._goto_step(4)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Plan", str(exc))
