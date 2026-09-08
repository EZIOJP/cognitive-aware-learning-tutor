"""Free time vs reward day vs gate mode — one place in CALT Desktop."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from backend.behavior.calt_desktop.widgets.gloss_panel import GlossPanel
from backend.behavior.calt_desktop.theme import muted_label, primary_button

if TYPE_CHECKING:
    from backend.behavior.tracker_service import TrackerService


class BrowseModesPanel(GlossPanel):
    """Clarifies gate mode, temporary free time (PIN), and earned reward days."""

    def __init__(self, service: TrackerService) -> None:
        super().__init__()
        self._service = service
        title = QLabel("Browse modes")
        title.setObjectName("sectionTitle")
        self.body_layout().addWidget(title)

        self._summary = QLabel("…")
        self._summary.setWordWrap(True)
        self.body_layout().addWidget(self._summary)

        self._reward_bar = QProgressBar()
        self._reward_bar.setRange(0, 100)
        self._reward_bar.setTextVisible(True)
        self._reward_bar.setFormat("Reward progress")
        self.body_layout().addWidget(self._reward_bar)

        self._reward_line = muted_label("")
        self._reward_line.setWordWrap(True)
        self.body_layout().addWidget(self._reward_line)

        row = QHBoxLayout()
        self._btn_free = QPushButton("Free time (PIN)…")
        self._btn_free.clicked.connect(self._on_free_time)
        row.addWidget(self._btn_free)

        self._btn_end_free = QPushButton("End free time")
        self._btn_end_free.clicked.connect(self._on_end_free)
        row.addWidget(self._btn_end_free)

        self._btn_reward = primary_button("Use reward day…")
        self._btn_reward.clicked.connect(self._on_reward_day)
        row.addWidget(self._btn_reward)
        row.addStretch(1)
        self.body_layout().addLayout(row)

        self.body_layout().addWidget(
            muted_label(
                "Mode FREE = gate allows leisure browsing (schedule, evening, or unlocked day). "
                "Free time = PIN override (blocked during incubation). "
                "Spend earned ledger minutes from the Dashboard. "
                "App kills = Windows enforcer · sites = CALT Gate."
            )
        )

    def _uid(self) -> int:
        return int(getattr(self._service, "user_id", 0) or 0)

    def refresh(self) -> None:
        uid = self._uid()
        if not uid:
            self._summary.setText("Waiting for tracker user…")
            self._reward_line.setText("")
            self._reward_bar.hide()
            return
        self._reward_bar.show()

        try:
            from backend.behavior.browser_gate_policy import free_override_until, mode_label
            from backend.behavior.reward_days import status

            gate = self._service.latest_gate() or {}
            browser = gate.get("browser") or {}
            mode = mode_label(str(browser.get("mode") or gate.get("browser_mode") or "free"))
            st = status(uid)
            until = free_override_until()
        except Exception as exc:  # noqa: BLE001
            self._summary.setText(str(exc))
            return

        override_s = f" · PIN override until {until.strftime('%H:%M')}" if until else ""
        reward_active = bool(st.get("active_today") or gate.get("reward_day"))
        parts = [f"Gate mode: {mode}{override_s}"]
        if reward_active:
            parts.append("Reward day active until midnight")
        elif gate.get("day_unlimited"):
            parts.append("Today unlocked (goal + Bible met)")
        self._summary.setText(" · ".join(parts))

        per = int(st.get("qualifying_days_per_reward") or 4)
        qual = int(st.get("qualifying_days") or 0)
        avail = int(st.get("available") or 0)
        next_n = int(st.get("days_to_next_reward") or per)
        mod = qual % per if per else 0
        pct = int(100 * mod / per) if per else 0
        self._reward_bar.setValue(pct)
        self._reward_bar.setFormat(
            f"Toward next credit: {mod}/{per} qualifying days"
            + (f" · {avail} banked" if avail else "")
        )
        self._reward_line.setText(
            f"Reward bank: {qual} qualifying day(s) · {avail} credit(s) available · "
            f"{next_n} more day(s) to earn next (goal + Bible chapter per day)"
        )

        self._btn_end_free.setEnabled(bool(until))
        self._btn_reward.setEnabled(avail > 0 and not reward_active)

    def _on_free_time(self) -> None:
        from backend.behavior.calt_desktop.dialogs import prompt_free_time

        if prompt_free_time(self.window()):
            self._service.latest_gate(force=True)
            self.refresh()

    def _on_end_free(self) -> None:
        try:
            from backend.behavior.browser_gate_policy import clear_free_override

            clear_free_override()
            self._service.latest_gate(force=True)
            self.refresh()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self.window(), "End free time", str(exc))

    def _on_reward_day(self) -> None:
        from PySide6.QtWidgets import QInputDialog

        from backend.behavior.reward_days import CONFIRM_PHRASE, claim_reward_day

        uid = self._uid()
        if not uid:
            return
        text, ok = QInputDialog.getText(
            self.window(),
            "Reward day",
            f"Type {CONFIRM_PHRASE} to activate an earned reward day until midnight:",
        )
        if not ok:
            return
        try:
            gate = self._service.latest_gate() or {}
            result = claim_reward_day(
                uid,
                confirm=text,
                already_unlocked=bool(gate.get("day_unlimited")),
            )
            self._service.latest_gate(force=True)
            QMessageBox.information(
                self.window(),
                "Reward day",
                str(result.get("message") or "Reward day active."),
            )
            self.refresh()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self.window(), "Reward day", str(exc))
