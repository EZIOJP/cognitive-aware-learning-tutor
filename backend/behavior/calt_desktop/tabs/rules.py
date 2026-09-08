"""Rules tab — hard block, blocked apps, categories, scores."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from backend.behavior.calt_desktop.navigation import go_tab
from backend.behavior.calt_desktop.theme import muted_label, primary_button
from backend.behavior.calt_desktop.widgets.rules_panels import (
    BlockedAppsEditor,
    CategoryPolicyTable,
    DeviceBlockInfo,
    GateStatusSummary,
    HardBlockSettings,
)
from backend.behavior.calt_desktop.widgets.section_header import PhaseBanner
from backend.behavior.calt_desktop.widgets.tab_lifecycle import VisiblePollMixin

if TYPE_CHECKING:
    from backend.behavior.tracker_service import TrackerService


def load_policy_for_user(user_id: int) -> dict[str, Any]:
    from backend.behavior.productivity_policy import load_policy_dict
    from backend.db.base import SessionLocal

    db = SessionLocal()
    try:
        return load_policy_dict(db, user_id)
    finally:
        db.close()


def save_policy_for_user(user_id: int, patch: dict[str, Any]) -> dict[str, Any]:
    from backend.behavior.productivity_policy import update_policy
    from backend.db.base import SessionLocal

    db = SessionLocal()
    try:
        return update_policy(db, user_id, patch)
    finally:
        db.close()


def load_scores() -> dict[str, int]:
    from backend.behavior.category_scores import load_score_map, seed_category_scores
    from backend.db.base import SessionLocal

    db = SessionLocal()
    try:
        seed_category_scores(db)
        return load_score_map(db)
    finally:
        db.close()


def save_scores(scores: dict[str, int]) -> None:
    from datetime import UTC, datetime

    from backend.db.base import SessionLocal
    from backend.models.category_score import CategoryScore

    db = SessionLocal()
    try:
        now = datetime.now(UTC)
        for category, score in scores.items():
            row = db.query(CategoryScore).filter(CategoryScore.category == category).first()
            if row is None:
                db.add(CategoryScore(category=category, score=int(score), updated_at=now))
            else:
                row.score = int(score)
                row.updated_at = now
        db.commit()
    finally:
        db.close()


class RulesTab(VisiblePollMixin, QWidget):
    REFRESH_MS = 30_000

    def __init__(self, service: TrackerService) -> None:
        super().__init__()
        self._service = service
        self._was_armed = False

        outer = QVBoxLayout(self)
        outer.setSpacing(8)

        head = QHBoxLayout()
        self._btn_save = primary_button("Save rules")
        self._btn_save.clicked.connect(self.save)
        head.addStretch(1)
        head.addWidget(self._btn_save)
        outer.addLayout(head)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        body = QWidget()
        lay = QVBoxLayout(body)
        lay.setSpacing(10)

        lay.addWidget(
            PhaseBanner(
                "Rules",
                "Hard block, blocked desktop apps, category scoring — shared with web Productivity page.",
            )
        )

        self._gate_status = GateStatusSummary()
        lay.addWidget(self._gate_status)

        self._hard_block = HardBlockSettings()
        lay.addWidget(self._hard_block)

        self._blocked_apps = BlockedAppsEditor()
        lay.addWidget(self._blocked_apps)

        self._categories = CategoryPolicyTable()
        lay.addWidget(self._categories)

        self._device_block = DeviceBlockInfo()
        lay.addWidget(self._device_block)

        nav = QHBoxLayout()
        btn_sched = QPushButton("Open gate schedules →")
        btn_sched.clicked.connect(lambda: go_tab("Schedules"))
        btn_today = QPushButton("Browse modes on Today →")
        btn_today.clicked.connect(lambda: go_tab("Today"))
        nav.addWidget(btn_sched)
        nav.addWidget(btn_today)
        nav.addStretch(1)
        lay.addLayout(nav)

        lay.addStretch(1)
        scroll.setWidget(body)
        outer.addWidget(scroll, stretch=1)

        foot = QHBoxLayout()
        btn_reload = QPushButton("Reload")
        btn_reload.clicked.connect(self.reload)
        foot.addWidget(btn_reload)
        self._status = muted_label("")
        foot.addWidget(self._status, stretch=1)
        outer.addLayout(foot)

        self._init_visible_poll(refresh=self.reload)

    def refresh(self) -> None:
        self.reload()

    def reload(self) -> None:
        uid = int(getattr(self._service, "user_id", 0) or 0)
        if not uid:
            self._status.setText("No tracker user yet — sign in via web app, then restart tracker if needed.")
            return
        try:
            policy = load_policy_for_user(uid)
            scores = load_scores()
            gate = self._service.latest_gate() or {}
        except Exception as exc:  # noqa: BLE001
            self._status.setText(f"Load failed: {exc}")
            return

        self._was_armed = bool(policy.get("hard_block_enabled"))
        self._hard_block.set_armed(self._was_armed)
        self._hard_block.set_goal(int(policy.get("daily_goal_minutes") or 240))
        self._blocked_apps.set_gaming(bool(policy.get("hard_block_gaming", True)))
        self._blocked_apps.set_exes(list(policy.get("hard_block_exes") or []))

        self._categories._table.blockSignals(True)
        try:
            self._categories._table.itemChanged.disconnect(self._categories._on_item_changed)
        except (RuntimeError, TypeError):
            pass
        self._categories.load(policy, scores)
        self._categories._table.itemChanged.connect(self._categories._on_item_changed)
        self._categories._table.blockSignals(False)

        self._gate_status.apply_gate(gate, policy=policy)
        self._device_block.refresh()
        n_exes = len(self._blocked_apps.exes())
        self._status.setText(f"Loaded · {n_exes} blocked exe(s) · {len(scores)} category scores.")

    def save(self) -> None:
        uid = int(getattr(self._service, "user_id", 0) or 0)
        if not uid:
            QMessageBox.warning(self, "Rules", "No tracker user id.")
            return
        if not self._hard_block.confirm_disarm_if_needed(was_armed=self._was_armed):
            return

        cat_patch, scores = self._categories.export()
        patch = {
            "hard_block_enabled": self._hard_block.armed(),
            "hard_block_gaming": self._blocked_apps.gaming(),
            "daily_goal_minutes": self._hard_block.goal_minutes(),
            "hard_block_exes": self._blocked_apps.exes(),
            **cat_patch,
        }
        try:
            save_policy_for_user(uid, patch)
            save_scores(scores)
            self._was_armed = bool(patch["hard_block_enabled"])
            try:
                self._service.latest_gate(force=True)
            except Exception:  # noqa: BLE001
                pass
            gate = self._service.latest_gate() or {}
            self._gate_status.apply_gate(gate, policy=patch)
            self._status.setText(
                f"Saved — goal {patch['daily_goal_minutes']} min · "
                f"{len(patch['hard_block_exes'])} blocked exe(s). Tracker picks up within ~30s."
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Rules", f"Save failed: {exc}")
