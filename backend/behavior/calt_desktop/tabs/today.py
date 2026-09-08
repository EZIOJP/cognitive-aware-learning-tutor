"""Today tab — gate glance, morning CTAs, quick toggles."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QLabel, QProgressBar, QVBoxLayout, QWidget

from backend.behavior.calt_desktop.navigation import go_tab
from backend.behavior.calt_desktop.theme import primary_button
from backend.behavior.calt_desktop.widgets.browse_modes_panel import BrowseModesPanel
from backend.behavior.calt_desktop.widgets.day_spine import DaySpinePanel
from backend.behavior.calt_desktop.widgets.gate_toggles import GateToggles
from backend.behavior.calt_desktop.widgets.gloss_panel import GlossPanel
from backend.behavior.calt_desktop.widgets.link_account_banner import LinkAccountBanner
from backend.behavior.calt_desktop.widgets.morning_ritual import MorningRitualPanel
from backend.behavior.calt_desktop.widgets.section_header import SectionHeader
from backend.behavior.calt_desktop.widgets.tab_lifecycle import VisiblePollMixin
from backend.behavior.calt_desktop.widgets.voice_agent_panel import VoiceAgentPanel

if TYPE_CHECKING:
    from backend.behavior.tracker_service import TrackerService

_MORNING_TAB: dict[str, str] = {
    "bible": "Bible",
    "plan": "Plan",
    "calendar": "Calendar",
}


class TodayTab(VisiblePollMixin, QWidget):
    REFRESH_MS = 10_000

    def __init__(self, service: TrackerService) -> None:
        super().__init__()
        self._service = service
        lay = QVBoxLayout(self)

        self._link_banner = LinkAccountBanner()
        lay.addWidget(self._link_banner)

        self._ritual = MorningRitualPanel(service)
        lay.addWidget(self._ritual)

        self._spine = DaySpinePanel(service)
        self._spine.block_action.connect(self._on_spine_action)
        lay.addWidget(self._spine)

        self._drift = QLabel("")
        self._drift.setWordWrap(True)
        self._drift.setObjectName("muted")
        lay.addWidget(self._drift)

        self._gate_status = QLabel("")
        self._gate_status.setWordWrap(True)
        self._gate_status.setObjectName("muted")
        lay.addWidget(self._gate_status)

        panel = GlossPanel()
        panel.body_layout().addWidget(
            SectionHeader(
                "Today at a glance",
                "Gate mode, focus goal, and morning flow — reward/free browsing is below.",
            )
        )
        self._mode = QLabel("Mode: …")
        self._mode.setObjectName("hero")
        self._focus = QLabel("Focus: …")
        self._morning = QLabel("Morning: …")
        for w in (self._mode, self._focus, self._morning):
            w.setWordWrap(True)
            panel.body_layout().addWidget(w)

        self._focus_bar = QProgressBar()
        self._focus_bar.setRange(0, 100)
        self._focus_bar.setTextVisible(True)
        panel.body_layout().addWidget(self._focus_bar)

        self._cta = primary_button("Continue morning flow")
        self._cta.clicked.connect(self._on_cta)
        panel.body_layout().addWidget(self._cta)
        lay.addWidget(panel)

        self._browse = BrowseModesPanel(service)
        lay.addWidget(self._browse)

        self._voice = VoiceAgentPanel(service)
        lay.addWidget(self._voice)

        self._gate = GateToggles(service)
        lay.addWidget(self._gate)
        lay.addStretch(1)

        self._next_key = "open"
        self._last_gate_block: str | None = None
        self._init_visible_poll()

    def _on_spine_action(self, action: str) -> None:
        if action != "apply_day":
            return
        uid = int(getattr(self._service, "user_id", 0) or 0)
        if not uid:
            self._drift.setText("Apply my day: sign in first.")
            return
        try:
            from backend.behavior.calt_desktop.day_coach import apply_my_day

            res = apply_my_day(uid)
            if res.get("ok"):
                self._drift.setText(
                    f"Applied day: +{res.get('routines_created', 0)} routines, "
                    f"+{res.get('study_created', 0)} study blocks "
                    f"(Revert on Plan tab)."
                )
                self._spine.refresh()
            else:
                self._drift.setText(str(res.get("error") or "Apply failed"))
        except Exception as exc:  # noqa: BLE001
            self._drift.setText(str(exc))

    def _on_cta(self) -> None:
        tab = _MORNING_TAB.get(self._next_key)
        if tab:
            go_tab(tab)
        else:
            go_tab("Plan")

    def refresh(self) -> None:
        try:
            gate = self._service.latest_gate() or {}
        except Exception:  # noqa: BLE001
            gate = {}
        browser = gate.get("browser") or {}
        mode = browser.get("mode") or gate.get("browser_mode") or "?"
        try:
            from backend.behavior.browser_gate_policy import mode_label

            mode_s = mode_label(str(mode))
        except Exception:  # noqa: BLE001
            mode_s = str(mode)
        self._mode.setText(f"Mode: {mode_s}")

        prod = gate.get("productive_minutes")
        goal = (gate.get("policy") or {}).get("daily_goal_minutes") or gate.get(
            "daily_goal_minutes"
        )
        if prod is None:
            try:
                prod = int((self._service.today_seconds() or 0) // 60)
            except Exception:  # noqa: BLE001
                prod = 0
        try:
            prod_i = int(prod)
        except (TypeError, ValueError):
            prod_i = 0
        try:
            goal_i = int(goal) if goal is not None else 240
        except (TypeError, ValueError):
            goal_i = 240
        goal_s = goal_i if goal is not None else "—"
        self._focus.setText(f"Focus: {prod_i} / {goal_s} productive minutes")
        pct = max(0, min(100, int(100 * prod_i / goal_i))) if goal_i else 0
        self._focus_bar.setValue(pct)
        self._focus_bar.setFormat(f"{pct}% of daily goal")

        morning = gate.get("morning") or {}
        nxt = str(morning.get("next") or "open")
        self._next_key = nxt
        try:
            from backend.behavior.tracker_rules import next_step_label

            nxt_s = next_step_label(nxt)
        except Exception:  # noqa: BLE001
            nxt_s = nxt
        plan_ok = morning.get("plan_confirmed") or morning.get("confirmed")
        self._morning.setText(f"Morning next: {nxt_s} · Plan confirmed: {'yes' if plan_ok else 'no'}")

        tab = _MORNING_TAB.get(nxt)
        if tab:
            self._cta.setText(f"Go to {tab} →")
            self._cta.setEnabled(True)
        elif plan_ok:
            self._cta.setText("Open Calendar →")
            self._cta.setEnabled(True)
            self._next_key = "calendar"
        else:
            self._cta.setText("Start Plan wizard →")
            self._cta.setEnabled(True)
            self._next_key = "plan"

        self._gate.refresh()
        self._browse.refresh()
        self._voice.refresh()
        self._ritual.refresh()
        self._spine.refresh()
        uid = int(getattr(self._service, "user_id", 0) or 0)
        self._link_banner.refresh(linked=uid > 0)
        if uid:
            try:
                from backend.behavior.calt_desktop.block_gate import apply_gate_for_active_block
                from backend.behavior.calt_desktop.day_coach import plan_drift_summary

                drift = plan_drift_summary(uid)
                if drift.get("lines"):
                    self._drift.setText(" · ".join(drift["lines"][:3]))
                else:
                    self._drift.setText(str(drift.get("summary") or ""))
                gate_msg = apply_gate_for_active_block(uid)
                if gate_msg and gate_msg != self._last_gate_block:
                    self._last_gate_block = gate_msg
                self._gate_status.setText(gate_msg or "")
            except Exception:  # noqa: BLE001
                pass
