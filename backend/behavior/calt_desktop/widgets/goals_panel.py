"""Goals panel — port of ProductivityGoalsPanel."""

from __future__ import annotations

import uuid
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from backend.behavior.calt_desktop.planner_api import load_goals, save_goals
from backend.behavior.calt_desktop.day_coach import current_week_key, ensure_weekly_goals
from backend.behavior.calt_desktop.study_task_presets import BLOCK_TEMPLATES
from backend.behavior.calt_desktop.theme import muted_label, primary_button
from backend.behavior.calt_desktop.widgets.section_header import SectionHeader


class GoalsPanel(QWidget):
    saved = Signal(dict)

    def __init__(self, user_id: int = 0, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._user_id = user_id
        lay = QVBoxLayout(self)
        lay.addWidget(
            SectionHeader(
                "Goals & motivation",
                "Weekly contract — study tasks reset each ISO week; old journeys not carried.",
                badge="Step 2",
            )
        )

        self._week_label = muted_label("")
        lay.addWidget(self._week_label)

        self._main = QPlainTextEdit()
        self._main.setMaximumHeight(72)
        lay.addWidget(QLabel("Main goal"))
        lay.addWidget(self._main)

        row = QHBoxLayout()
        row.addWidget(QLabel("Focus h/day"))
        self._focus = QSpinBox()
        self._focus.setRange(1, 16)
        row.addWidget(self._focus)
        row.addWidget(QLabel("Weekly h"))
        self._weekly = QSpinBox()
        self._weekly.setRange(1, 80)
        row.addWidget(self._weekly)
        row.addStretch(1)
        lay.addLayout(row)

        lay.addWidget(QLabel("Study tasks (today's blocks — not old journeys)"))
        self._tasks = QListWidget()
        self._tasks.setMaximumHeight(120)
        lay.addWidget(self._tasks)
        task_row = QHBoxLayout()
        for label, _tip, factory in BLOCK_TEMPLATES:
            btn = QPushButton(f"+ {label}")
            btn.clicked.connect(lambda _c, f=factory: self._add_template(f))
            task_row.addWidget(btn)
        btn_task = QPushButton("+ Custom")
        btn_task.clicked.connect(self._add_custom_task)
        task_row.addWidget(btn_task)
        task_row.addStretch(1)
        lay.addWidget(muted_label(
            "Each task: title, minutes, allowed hosts (Scaler rules), blocked categories during block."
        ))
        lay.addLayout(task_row)

        lay.addWidget(QLabel("Reward"))
        self._reward = QLineEdit()
        lay.addWidget(self._reward)

        lay.addWidget(QLabel("Extra goals / todos"))
        self._extras = QListWidget()
        self._extras.setMaximumHeight(100)
        lay.addWidget(self._extras)
        ex_row = QHBoxLayout()
        self._extra_in = QLineEdit()
        self._extra_in.setPlaceholderText("Add side goal…")
        btn_add = QPushButton("Add")
        btn_add.clicked.connect(self._add_extra)
        ex_row.addWidget(self._extra_in)
        ex_row.addWidget(btn_add)
        lay.addLayout(ex_row)

        self._status = muted_label("")
        lay.addWidget(self._status)

        btn_save = primary_button("Save goals")
        btn_save.clicked.connect(self.save)
        lay.addWidget(btn_save)

        self.reload()

    def set_user_id(self, user_id: int) -> None:
        self._user_id = user_id

    def reload(self) -> None:
        g = ensure_weekly_goals()
        self._week_label.setText(f"Week {current_week_key()} · save updates gate minutes in DB")
        self._main.setPlainText(str(g.get("mainGoal") or ""))
        self._focus.setValue(int(g.get("focusHoursPerDay") or 4))
        self._weekly.setValue(int(g.get("weeklyFocusHours") or 24))
        self._reward.setText(str(g.get("reward") or ""))
        self._extras.clear()
        self._tasks.clear()
        for item in g.get("studyTasks") or []:
            if isinstance(item, dict) and str(item.get("title") or "").strip():
                row = QListWidgetItem(self._task_label(item))
                row.setData(256, item)
                self._tasks.addItem(row)
        for item in g.get("extraGoals") or []:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            if not title:
                continue
            row = QListWidgetItem(title)
            row.setData(256, item)
            row.setCheckState(
                Qt.CheckState.Checked if item.get("done") else Qt.CheckState.Unchecked
            )
            self._extras.addItem(row)

    @staticmethod
    def _task_label(item: dict) -> str:
        return (
            f"{item.get('title')} · {int(item.get('minutes') or 60)}m · "
            f"allow {len(item.get('allowHosts') or [])} sites"
        )

    def goals_dict(self) -> dict[str, Any]:
        extras: list[dict[str, Any]] = []
        tasks: list[dict[str, Any]] = []
        for i in range(self._tasks.count()):
            item = self._tasks.item(i)
            if item is None:
                continue
            data = item.data(256) or {}
            if isinstance(data, dict):
                tasks.append(data)
        for i in range(self._extras.count()):
            item = self._extras.item(i)
            if item is None:
                continue
            data = item.data(256) or {}
            extras.append(
                {
                    "id": data.get("id") or f"g-{uuid.uuid4().hex[:8]}",
                    "title": item.text(),
                    "done": item.checkState() == Qt.CheckState.Checked,
                }
            )
        return {
            "mainGoal": self._main.toPlainText().strip(),
            "focusHoursPerDay": int(self._focus.value()),
            "weeklyFocusHours": int(self._weekly.value()),
            "reward": self._reward.text().strip(),
            "extraGoals": extras,
            "studyTasks": tasks,
        }

    def save(self) -> None:
        data = self.goals_dict()
        merged = save_goals(data, user_id=self._user_id or None)
        self._status.setText("Saved · gate daily goal updated")
        self.saved.emit(merged)

    def _add_extra(self) -> None:
        title = self._extra_in.text().strip()
        if not title:
            return
        item = QListWidgetItem(title)
        item.setData(256, {"id": f"g-{uuid.uuid4().hex[:8]}", "title": title, "done": False})
        self._extras.addItem(item)
        self._extra_in.clear()

    def _add_template(self, factory) -> None:
        task = factory()
        row = QListWidgetItem(self._task_label(task))
        row.setData(256, task)
        self._tasks.addItem(row)

    def _add_scaler_task(self) -> None:
        from backend.behavior.calt_desktop.study_task_presets import scaler_study_task

        task = scaler_study_task()
        row = QListWidgetItem(self._task_label(task))
        row.setData(256, task)
        self._tasks.addItem(row)

    def _add_custom_task(self) -> None:
        title = self._extra_in.text().strip() or "Study block"
        task = {
            "id": f"task-{uuid.uuid4().hex[:8]}",
            "title": title,
            "minutes": 60,
            "allowHosts": ["scaler.com", "colab.research.google.com", "github.com"],
            "blockCategories": ["Gaming", "Video Streaming", "Social Media", "Entertainment"],
        }
        row = QListWidgetItem(self._task_label(task))
        row.setData(256, task)
        self._tasks.addItem(row)
        self._extra_in.clear()
