"""Rules tab — hard block + daily goal + category scores."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

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


class RulesTab(QWidget):
    def __init__(self, service: TrackerService) -> None:
        super().__init__()
        self._service = service
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Rules — hard block, goal, category scores"))
        form = QFormLayout()
        self._armed = QCheckBox("Hard block enabled")
        self._gaming = QCheckBox("Block gaming / distraction exes")
        self._goal = QSpinBox()
        self._goal.setRange(30, 720)
        self._goal.setSuffix(" min")
        self._exes = QLineEdit()
        self._exes.setPlaceholderText("comma-separated exes, e.g. steam.exe")
        form.addRow(self._armed)
        form.addRow(self._gaming)
        form.addRow("Daily focus goal", self._goal)
        form.addRow("Extra kill exes", self._exes)
        lay.addLayout(form)

        lay.addWidget(QLabel("Category scores (edit Score column)"))
        self._table = QTableWidget(0, 2)
        self._table.setHorizontalHeaderLabels(["Category", "Score"])
        self._table.horizontalHeader().setStretchLastSection(True)
        lay.addWidget(self._table)

        row = QHBoxLayout()
        btn_load = QPushButton("Reload")
        btn_load.clicked.connect(self.reload)
        btn_save = QPushButton("Save")
        btn_save.clicked.connect(self.save)
        row.addWidget(btn_load)
        row.addWidget(btn_save)
        row.addStretch(1)
        lay.addLayout(row)
        self._status = QLabel("")
        self._status.setStyleSheet("color: #94a3b8;")
        lay.addWidget(self._status)
        self.reload()

    def _fill_scores(self, scores: dict[str, int]) -> None:
        keys = sorted(scores.keys())
        self._table.setRowCount(len(keys))
        for i, cat in enumerate(keys):
            cat_item = QTableWidgetItem(cat)
            cat_item.setFlags(cat_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._table.setItem(i, 0, cat_item)
            self._table.setItem(i, 1, QTableWidgetItem(str(int(scores[cat]))))

    def _read_scores_from_table(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for i in range(self._table.rowCount()):
            cat_item = self._table.item(i, 0)
            score_item = self._table.item(i, 1)
            if not cat_item:
                continue
            cat = cat_item.text().strip()
            try:
                score = int((score_item.text() if score_item else "35").strip() or 35)
            except ValueError:
                score = 35
            out[cat] = max(0, min(100, score))
        return out

    def reload(self) -> None:
        uid = int(getattr(self._service, "user_id", 0) or 0)
        if not uid:
            self._status.setText("No tracker user yet — wait for session start.")
            return
        try:
            policy = load_policy_for_user(uid)
            scores = load_scores()
        except Exception as exc:  # noqa: BLE001
            self._status.setText(f"Load failed: {exc}")
            return
        self._armed.setChecked(bool(policy.get("hard_block_enabled")))
        self._gaming.setChecked(bool(policy.get("hard_block_gaming", True)))
        self._goal.setValue(int(policy.get("daily_goal_minutes") or 240))
        exes = policy.get("hard_block_exes") or []
        if isinstance(exes, list):
            self._exes.setText(", ".join(str(x) for x in exes))
        else:
            self._exes.setText(str(exes))
        self._fill_scores(scores)
        self._status.setText(f"Loaded ({len(scores)} categories).")

    def save(self) -> None:
        uid = int(getattr(self._service, "user_id", 0) or 0)
        if not uid:
            QMessageBox.warning(self, "Rules", "No tracker user id.")
            return
        exes = [x.strip() for x in self._exes.text().split(",") if x.strip()]
        patch = {
            "hard_block_enabled": self._armed.isChecked(),
            "hard_block_gaming": self._gaming.isChecked(),
            "daily_goal_minutes": int(self._goal.value()),
            "hard_block_exes": exes,
        }
        try:
            save_policy_for_user(uid, patch)
            save_scores(self._read_scores_from_table())
            self._status.setText("Saved policy + scores.")
            try:
                self._service.latest_gate(force=True)
            except Exception:  # noqa: BLE001
                pass
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Rules", f"Save failed: {exc}")
