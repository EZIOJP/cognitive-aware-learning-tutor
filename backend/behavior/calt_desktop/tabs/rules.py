"""Rules tab — hard block + daily goal (core policy fields)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
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


class RulesTab(QWidget):
    def __init__(self, service: TrackerService) -> None:
        super().__init__()
        self._service = service
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Rules — hard block & daily goal"))
        form = QFormLayout()
        self._armed = QCheckBox("Hard block enabled")
        self._gaming = QCheckBox("Block gaming / distraction exes")
        self._goal = QSpinBox()
        self._goal.setRange(30, 720)
        self._goal.setSuffix(" min")
        self._exes = QLineEdit()
        self._exes.setPlaceholderText("comma-separated exes, e.g. steam.exe, epicgameslauncher.exe")
        form.addRow(self._armed)
        form.addRow(self._gaming)
        form.addRow("Daily focus goal", self._goal)
        form.addRow("Extra kill exes", self._exes)
        lay.addLayout(form)

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
        lay.addStretch(1)
        self.reload()

    def reload(self) -> None:
        uid = int(getattr(self._service, "user_id", 0) or 0)
        if not uid:
            self._status.setText("No tracker user yet — wait for session start.")
            return
        try:
            policy = load_policy_for_user(uid)
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
        self._status.setText("Loaded.")

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
            self._status.setText("Saved.")
            try:
                self._service.latest_gate(force=True)
            except Exception:  # noqa: BLE001
                pass
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Rules", f"Save failed: {exc}")
