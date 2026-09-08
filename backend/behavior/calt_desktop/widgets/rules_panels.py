"""Reusable Rules tab panels — hard block, blocked exes, category policy."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from backend.behavior.calt_desktop.theme import muted_label, primary_button
from backend.behavior.calt_desktop.widgets.gloss_panel import GlossPanel
from backend.behavior.calt_desktop.widgets.section_header import SectionHeader

_COMMON_CATEGORIES = [
    "IDE / Code Editor",
    "Terminal",
    "Dev Tools",
    "Coding Practice",
    "Study / Reading",
    "Study (Browser)",
    "Coursework (Browser)",
    "AI Tools",
    "AI / ML",
    "Research",
    "Documentation",
    "Knowledge Work",
    "Office / Docs",
    "Gaming",
    "Video Streaming",
    "Music / Media",
    "Social Media",
    "Entertainment",
    "Shopping",
    "Browser",
    "Communication",
    "Other",
]


class GateStatusSummary(GlossPanel):
    """Live gate snapshot — read-only context for Rules."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.body_layout().addWidget(
            SectionHeader(
                "Gate right now",
                "Browser mode + focus progress. Changes here when you save policy or complete morning flow.",
            )
        )
        self._line1 = QLabel("…")
        self._line1.setWordWrap(True)
        self._line2 = muted_label("")
        self._line2.setWordWrap(True)
        self.body_layout().addWidget(self._line1)
        self.body_layout().addWidget(self._line2)

    def apply_gate(self, gate: dict[str, Any] | None, *, policy: dict[str, Any] | None = None) -> None:
        g = gate or {}
        pol = policy or {}
        browser = g.get("browser") if isinstance(g.get("browser"), dict) else {}
        try:
            from backend.behavior.browser_gate_policy import mode_label

            mode = mode_label(str(browser.get("mode") or g.get("browser_mode") or "—"))
        except Exception:  # noqa: BLE001
            mode = str(browser.get("mode") or g.get("browser_mode") or "—")

        prod = int(g.get("productive_minutes") or 0)
        goal = int(pol.get("daily_goal_minutes") or g.get("daily_goal_minutes") or 240)
        remain = max(0, goal - prod)
        locked = "locked" if g.get("locked") else "open"
        armed = "armed" if pol.get("hard_block_enabled") else "disarmed"

        self._line1.setText(
            f"Mode {mode} · Gate {locked} · Hard block {armed} · "
            f"Focus {prod}/{goal} min ({remain} min to goal)"
        )

        morning = g.get("morning") if isinstance(g.get("morning"), dict) else {}
        parts: list[str] = []
        if morning.get("next"):
            try:
                from backend.behavior.tracker_rules import next_step_label

                parts.append(f"Morning: {next_step_label(str(morning.get('next')))}")
            except Exception:  # noqa: BLE001
                parts.append(f"Morning next: {morning.get('next')}")
        if g.get("reward_day"):
            parts.append("Reward day active")
        if browser.get("free_override_active"):
            parts.append("PIN free-time override")
        hb = g.get("hard_block") if isinstance(g.get("hard_block"), dict) else {}
        if hb.get("blocked_recently"):
            parts.append(f"Last blocked: {hb.get('last_exe') or 'app'}")
        self._line2.setText(" · ".join(parts) if parts else "Edge extension enforces site blocks while gate is locked.")


class BlockedAppsEditor(GlossPanel):
    """Desktop .exe kill list when hard block is armed."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.body_layout().addWidget(
            SectionHeader(
                "Blocked desktop apps",
                "Games and distraction clients killed when hard block is armed "
                "(Windows enforcer owns kills). "
                "Browsers are never on this list — Edge uses CALT Gate SoftLand.",
            )
        )
        self._gaming = QCheckBox("Also block Gaming / Video / Social categories (desktop apps)")
        self.body_layout().addWidget(self._gaming)

        self._list = QListWidget()
        self._list.setMinimumHeight(140)
        self.body_layout().addWidget(self._list)

        row = QHBoxLayout()
        self._new_exe = QLineEdit()
        self._new_exe.setPlaceholderText("Add exe, e.g. valorant.exe")
        row.addWidget(self._new_exe, stretch=1)
        btn_add = QPushButton("Add")
        btn_add.clicked.connect(self._add_exe)
        row.addWidget(btn_add)
        btn_rm = QPushButton("Remove")
        btn_rm.clicked.connect(self._remove_selected)
        row.addWidget(btn_rm)
        btn_def = QPushButton("Restore defaults")
        btn_def.clicked.connect(self._restore_defaults)
        row.addWidget(btn_def)
        self.body_layout().addLayout(row)

        self.body_layout().addWidget(
            muted_label(
                "Tip: Task Manager → Details shows process names. "
                "Steam/Epic/Discord are in the default seed list."
            )
        )

    def _add_exe(self) -> None:
        name = self._new_exe.text().strip()
        if not name:
            return
        if not name.lower().endswith(".exe"):
            name = f"{name}.exe"
        existing = {self._list.item(i).text().lower() for i in range(self._list.count())}
        if name.lower() not in existing:
            self._list.addItem(name)
        self._new_exe.clear()

    def _remove_selected(self) -> None:
        for item in self._list.selectedItems():
            self._list.takeItem(self._list.row(item))

    def _restore_defaults(self) -> None:
        from backend.behavior.distraction_gate import DEFAULT_HARD_BLOCK_EXES

        self.set_exes(list(DEFAULT_HARD_BLOCK_EXES))

    def set_exes(self, exes: list[str]) -> None:
        self._list.clear()
        for exe in sorted({str(x).strip() for x in exes if str(x).strip()}, key=str.lower):
            self._list.addItem(exe)

    def exes(self) -> list[str]:
        return [self._list.item(i).text().strip() for i in range(self._list.count()) if self._list.item(i)]

    def set_gaming(self, on: bool) -> None:
        self._gaming.setChecked(bool(on))

    def gaming(self) -> bool:
        return self._gaming.isChecked()


class CategoryPolicyTable(GlossPanel):
    """Productive vs blocked categories + per-category scores."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.body_layout().addWidget(
            SectionHeader(
                "Category scoring",
                "Blocked categories never count as productive. Productive list boosts focus credit. "
                "Score column feeds the tracker threshold (default 35).",
            )
        )
        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["Category", "Productive", "Blocked", "Score"])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setMinimumHeight(220)
        self.body_layout().addWidget(self._table)

    def _all_categories(self, policy: dict[str, Any], scores: dict[str, int]) -> list[str]:
        productive = policy.get("productive_categories") or []
        blocked = policy.get("blocked_categories") or []
        keys = set(_COMMON_CATEGORIES) | set(scores.keys()) | set(productive) | set(blocked)
        return sorted(keys)

    def load(self, policy: dict[str, Any], scores: dict[str, int]) -> None:
        productive = set(policy.get("productive_categories") or [])
        blocked = set(policy.get("blocked_categories") or [])
        cats = self._all_categories(policy, scores)
        self._table.setRowCount(len(cats))
        for row, cat in enumerate(cats):
            name_item = QTableWidgetItem(cat)
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._table.setItem(row, 0, name_item)

            prod_item = QTableWidgetItem()
            prod_item.setFlags(
                Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled
            )
            prod_item.setCheckState(
                Qt.CheckState.Checked if cat in productive else Qt.CheckState.Unchecked
            )
            self._table.setItem(row, 1, prod_item)

            block_item = QTableWidgetItem()
            block_item.setFlags(
                Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled
            )
            block_item.setCheckState(
                Qt.CheckState.Checked if cat in blocked else Qt.CheckState.Unchecked
            )
            self._table.setItem(row, 2, block_item)

            score_item = QTableWidgetItem(str(int(scores.get(cat, 35))))
            self._table.setItem(row, 3, score_item)

        self._table.itemChanged.connect(self._on_item_changed)

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if item.column() not in (1, 2):
            return
        row = item.row()
        other_col = 2 if item.column() == 1 else 1
        if item.checkState() == Qt.CheckState.Checked:
            other = self._table.item(row, other_col)
            if other and other.checkState() == Qt.CheckState.Checked:
                self._table.blockSignals(True)
                other.setCheckState(Qt.CheckState.Unchecked)
                self._table.blockSignals(False)

    def export(self) -> tuple[dict[str, Any], dict[str, int]]:
        productive: list[str] = []
        blocked: list[str] = []
        scores: dict[str, int] = {}
        for row in range(self._table.rowCount()):
            cat_item = self._table.item(row, 0)
            if not cat_item:
                continue
            cat = cat_item.text().strip()
            prod = self._table.item(row, 1)
            block = self._table.item(row, 2)
            score_item = self._table.item(row, 3)
            if prod and prod.checkState() == Qt.CheckState.Checked:
                productive.append(cat)
            if block and block.checkState() == Qt.CheckState.Checked:
                blocked.append(cat)
            try:
                score = int((score_item.text() if score_item else "35").strip() or 35)
            except ValueError:
                score = 35
            scores[cat] = max(0, min(100, score))
        policy_patch = {
            "productive_categories": productive,
            "blocked_categories": blocked,
        }
        return policy_patch, scores


class DeviceBlockInfo(GlossPanel):
    """Read-only device-wide hosts block status."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.body_layout().addWidget(
            SectionHeader(
                "Device-wide adult block",
                "Hosts-file block (all apps). Porn domains only — YouTube uses browser gate, not hosts.",
            )
        )
        self._summary = QLabel("…")
        self._summary.setWordWrap(True)
        self.body_layout().addWidget(self._summary)
        self.body_layout().addWidget(
            muted_label("Managed in tracker sync — edit data/behavior/device_block.json if needed.")
        )

    def refresh(self) -> None:
        try:
            from backend.behavior.device_block import status as device_status
            from backend.behavior.porn_blocklist import cached_domains, load_cache

            st = device_status()
            settings = st.get("settings") or {}
            cache = load_cache()
            domain_n = len(cached_domains())
            active = "active" if st.get("active") else "not in hosts"
            enabled = "on" if settings.get("enabled") else "off"
            self._summary.setText(
                f"Device block {enabled} · {active} · "
                f"{st.get('managed_host_entries', 0)} hosts entries · "
                f"{domain_n} cached domains"
                + (
                    f" · cache updated {cache.get('fetched_at', '—')[:10]}"
                    if cache.get("fetched_at")
                    else ""
                )
            )
        except Exception as exc:  # noqa: BLE001
            self._summary.setText(str(exc))


class HardBlockSettings(GlossPanel):
    """Armed toggle + daily goal."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.body_layout().addWidget(
            SectionHeader(
                "Hard block until daily goal",
                "Kills listed desktop apps until focus goal + Bible chapter (or reward day / PIN override).",
            )
        )
        self._armed = QCheckBox("Hard block armed")
        self.body_layout().addWidget(self._armed)

        goal_row = QHBoxLayout()
        goal_row.addWidget(QLabel("Daily focus goal"))
        self._goal = QSpinBox()
        self._goal.setRange(30, 720)
        self._goal.setSuffix(" min")
        goal_row.addWidget(self._goal)
        goal_row.addStretch(1)
        self.body_layout().addLayout(goal_row)

        self.body_layout().addWidget(
            muted_label(
                "Disarming requires typing UNLOCK — same as web Rules. "
                "Games unlock after goal + today's Bible chapter, or use a reward day on Today tab."
            )
        )

    def set_armed(self, on: bool) -> None:
        self._armed.setChecked(bool(on))

    def armed(self) -> bool:
        return self._armed.isChecked()

    def set_goal(self, minutes: int) -> None:
        self._goal.setValue(int(minutes))

    def goal_minutes(self) -> int:
        return int(self._goal.value())

    def confirm_disarm_if_needed(self, *, was_armed: bool) -> bool:
        """Return False if user cancelled UNLOCK prompt."""
        if was_armed and not self._armed.isChecked():
            from PySide6.QtWidgets import QInputDialog

            text, ok = QInputDialog.getText(
                self.window(),
                "Disarm hard block",
                "Type UNLOCK to turn off hard block:",
            )
            if not ok or text.strip() != "UNLOCK":
                self._armed.setChecked(True)
                return False
        return True
