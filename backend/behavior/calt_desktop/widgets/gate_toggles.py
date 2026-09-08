"""Quick enable/disable for hard block and recurring gate schedules."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QPushButton

from backend.behavior.calt_desktop.navigation import go_tab
from backend.behavior.calt_desktop.theme import muted_label
from backend.behavior.calt_desktop.widgets.gloss_panel import GlossPanel
from backend.behavior.calt_desktop.widgets.section_header import SectionHeader

if TYPE_CHECKING:
    from backend.behavior.tracker_service import TrackerService


class GateToggles(GlossPanel):
    def __init__(self, service: TrackerService) -> None:
        super().__init__()
        self._service = service
        self.body_layout().addWidget(
            SectionHeader(
                "Gate controls",
                "Quick toggles — edit blocked apps and categories on the Rules tab.",
            )
        )

        row = QHBoxLayout()
        self._hard_block = QCheckBox("Hard block armed")
        self._hard_block.toggled.connect(self._on_hard_block)
        row.addWidget(self._hard_block)

        self._schedules = QCheckBox("Recurring schedules")
        self._schedules.toggled.connect(self._on_schedules)
        row.addWidget(self._schedules)
        row.addStretch(1)
        self.body_layout().addLayout(row)

        self._detail = muted_label("")
        self._detail.setWordWrap(True)
        self.body_layout().addWidget(self._detail)

        nav = QHBoxLayout()
        btn_rules = QPushButton("Rules — blocked apps & categories →")
        btn_rules.clicked.connect(lambda: go_tab("Rules"))
        btn_sched = QPushButton("Schedules →")
        btn_sched.clicked.connect(lambda: go_tab("Schedules"))
        nav.addWidget(btn_rules)
        nav.addWidget(btn_sched)
        nav.addStretch(1)
        self.body_layout().addLayout(nav)

    def refresh(self) -> None:
        uid = int(getattr(self._service, "user_id", 0) or 0)
        if not uid:
            self._detail.setText("Waiting for tracker user…")
            return
        try:
            from backend.behavior.calt_desktop.tabs.rules import load_policy_for_user
            from backend.behavior.gate_schedules import load_gate_schedules

            policy = load_policy_for_user(uid)
            schedules = load_gate_schedules()
            gate = self._service.latest_gate() or {}
        except Exception as exc:  # noqa: BLE001
            self._detail.setText(str(exc))
            return

        self._hard_block.blockSignals(True)
        self._schedules.blockSignals(True)
        self._hard_block.setChecked(bool(policy.get("hard_block_enabled")))
        self._schedules.setChecked(bool(schedules.get("enabled")))
        self._hard_block.blockSignals(False)
        self._schedules.blockSignals(False)

        n_exes = len(policy.get("hard_block_exes") or [])
        n_blocked = len(policy.get("blocked_categories") or [])
        mode = "—"
        try:
            from backend.behavior.browser_gate_policy import mode_label

            browser = gate.get("browser") or {}
            mode = mode_label(str(browser.get("mode") or gate.get("browser_mode") or "—"))
        except Exception:  # noqa: BLE001
            pass
        self._detail.setText(
            f"Browser mode {mode} · {n_exes} blocked exe(s) · {n_blocked} blocked categories · "
            "Schedules switch study/free/planning by time window."
        )

    def _on_hard_block(self, checked: bool) -> None:
        uid = int(getattr(self._service, "user_id", 0) or 0)
        if not uid:
            return
        if not checked:
            from PySide6.QtWidgets import QInputDialog

            text, ok = QInputDialog.getText(
                self.window(),
                "Disarm hard block",
                "Type UNLOCK to turn off hard block:",
            )
            if not ok or text.strip() != "UNLOCK":
                self._hard_block.blockSignals(True)
                self._hard_block.setChecked(True)
                self._hard_block.blockSignals(False)
                return
        try:
            from backend.behavior.calt_desktop.tabs.rules import save_policy_for_user

            save_policy_for_user(uid, {"hard_block_enabled": checked})
            self._service.latest_gate(force=True)
            self.refresh()
        except Exception as exc:  # noqa: BLE001
            self._detail.setText(f"Hard block save failed: {exc}")

    def _on_schedules(self, checked: bool) -> None:
        try:
            from backend.behavior.gate_schedules import load_gate_schedules, save_gate_schedules

            data = load_gate_schedules()
            data["enabled"] = checked
            save_gate_schedules(data)
            self._service.latest_gate(force=True)
            self.refresh()
        except Exception as exc:  # noqa: BLE001
            self._detail.setText(f"Schedules save failed: {exc}")
