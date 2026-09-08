"""Routine editor — inline edit, morning-first reorder, no modal dialogs."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from backend.behavior.calt_desktop.planner_api import (
    ROUTINE_DAYS,
    apply_routines_today,
    create_routine,
    delete_routine,
    list_routines,
    reorder_morning_routines,
    reorder_routine_ids,
    seed_routine_defaults,
    update_routine,
)
from backend.behavior.calt_desktop.theme import muted_label, primary_button
from backend.behavior.calt_desktop.widgets.section_header import SectionHeader

_CATEGORIES = ["spiritual", "food", "personal", "break", "study"]
_DAY_LABELS = "MTWTFSS"


class RoutinesPanel(QWidget):
    changed = Signal()

    def __init__(self, user_id: int = 0, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._user_id = user_id
        self._editing_id: int | None = None
        self._row_ids: list[int] = []
        lay = QVBoxLayout(self)
        lay.addWidget(
            SectionHeader(
                "Daily routines",
                "Life blocks only — Apply for today adds today's rows (skips overlaps; does not copy yesterday's study).",
                badge="Step 1",
            )
        )
        self._status = muted_label("Load routines when you open this step.")
        lay.addWidget(self._status)

        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels(["#", "On", "Title", "Time", "Category", "Actions"])
        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(0, 28)
        self._table.setColumnWidth(1, 36)
        self._table.setColumnWidth(5, 168)
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)
        lay.addWidget(self._table)

        editor = QWidget()
        form = QFormLayout(editor)
        self._title = QLineEdit()
        self._start = QLineEdit("06:00")
        self._end = QLineEdit("06:30")
        self._mins = QSpinBox()
        self._mins.setRange(5, 480)
        self._mins.setValue(30)
        self._cat = QComboBox()
        self._cat.addItems(_CATEGORIES)
        self._enabled = QCheckBox("Enabled")
        self._enabled.setChecked(True)
        self._day_checks: list[QCheckBox] = []
        day_row = QHBoxLayout()
        for i, _d in enumerate(ROUTINE_DAYS):
            cb = QCheckBox(_DAY_LABELS[i])
            cb.setChecked(True)
            self._day_checks.append(cb)
            day_row.addWidget(cb)
        form.addRow("Title", self._title)
        times = QHBoxLayout()
        times.addWidget(self._start)
        times.addWidget(QLabel("–"))
        times.addWidget(self._end)
        form.addRow("Time", times)
        form.addRow("Duration min", self._mins)
        form.addRow("Category", self._cat)
        form.addRow("Days", day_row)
        form.addRow("", self._enabled)
        lay.addWidget(editor)

        erow = QHBoxLayout()
        self._btn_save = primary_button("Save routine")
        self._btn_save.clicked.connect(self._save_inline)
        self._btn_clear = QPushButton("Clear form")
        self._btn_clear.clicked.connect(self._clear_form)
        erow.addWidget(self._btn_save)
        erow.addWidget(self._btn_clear)
        erow.addStretch(1)
        lay.addLayout(erow)

        row = QHBoxLayout()
        btn_seed = QPushButton("Seed defaults")
        btn_seed.clicked.connect(self._seed)
        btn_reorder = QPushButton("Reorder morning-first")
        btn_reorder.clicked.connect(self._reorder)
        btn_add = QPushButton("New")
        btn_add.clicked.connect(self._clear_form)
        btn_apply = primary_button("Apply for today")
        btn_apply.clicked.connect(self._apply)
        for b in (btn_seed, btn_reorder, btn_add, btn_apply):
            row.addWidget(b)
        row.addStretch(1)
        lay.addLayout(row)

        if user_id:
            self.reload()

    def set_user_id(self, user_id: int) -> None:
        self._user_id = user_id
        self.reload()

    def reload(self) -> None:
        uid = self._user_id
        if not uid:
            self._status.setText("No user yet — sign in via web app.")
            self._table.setRowCount(0)
            return
        try:
            rows = sorted(
                list_routines(uid),
                key=lambda r: (
                    int(r.get("sort_order") or 0),
                    str(r.get("start_time") or ""),
                ),
            )
        except Exception as exc:  # noqa: BLE001
            self._status.setText(str(exc))
            return
        enabled = sum(1 for r in rows if r.get("enabled"))
        self._status.setText(
            f"{len(rows)} routine(s) · {enabled} enabled · "
            "Rule: day starts with routines (Bible first) · break after every study task."
        )
        self._table.setRowCount(len(rows))
        self._row_ids = []
        for i, r in enumerate(rows):
            rid = int(r.get("id") or 0)
            self._row_ids.append(rid)
            num = QTableWidgetItem(str(i + 1))
            num.setFlags(num.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._table.setItem(i, 0, num)

            on = QTableWidgetItem()
            on.setFlags(on.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            on.setCheckState(
                Qt.CheckState.Checked if r.get("enabled") else Qt.CheckState.Unchecked
            )
            on.setData(Qt.ItemDataRole.UserRole, int(r.get("id") or 0))
            self._table.setItem(i, 1, on)

            title_item = QTableWidgetItem(str(r.get("title") or ""))
            title_item.setToolTip(str(r.get("title") or ""))
            self._table.setItem(i, 2, title_item)

            st = str(r.get("start_time") or "")
            en = str(r.get("end_time") or "")
            self._table.setItem(i, 3, QTableWidgetItem(f"{st} – {en}" if en else st))
            self._table.setItem(i, 4, QTableWidgetItem(str(r.get("category") or "")))

            rid = int(r.get("id") or 0)
            cell = QWidget()
            h = QHBoxLayout(cell)
            h.setContentsMargins(2, 0, 2, 0)
            h.setSpacing(4)
            btn_edit = QPushButton("Edit")
            btn_edit.setObjectName("navChip")
            btn_edit.setFixedWidth(44)
            btn_edit.clicked.connect(lambda _c, routine=r: self._load_form(routine))
            btn_up = QPushButton("↑")
            btn_up.setObjectName("navChip")
            btn_up.setFixedWidth(24)
            btn_up.setEnabled(i > 0)
            btn_up.clicked.connect(lambda _c, idx=i: self._move_row(idx, -1))
            btn_dn = QPushButton("↓")
            btn_dn.setObjectName("navChip")
            btn_dn.setFixedWidth(24)
            btn_dn.setEnabled(i < len(rows) - 1)
            btn_dn.clicked.connect(lambda _c, idx=i: self._move_row(idx, 1))
            btn_del = QPushButton("×")
            btn_del.setObjectName("navChip")
            btn_del.setFixedWidth(24)
            btn_del.clicked.connect(lambda _c, routine_id=rid: self._delete(routine_id))
            h.addWidget(btn_up)
            h.addWidget(btn_dn)
            h.addWidget(btn_edit)
            h.addWidget(btn_del)
            self._table.setCellWidget(i, 5, cell)

    def _payload(self) -> dict:
        days = [ROUTINE_DAYS[i] for i, cb in enumerate(self._day_checks) if cb.isChecked()]
        if not days:
            days = list(ROUTINE_DAYS)
        return {
            "title": self._title.text().strip() or "Routine",
            "start_time": self._start.text().strip() or "09:00",
            "end_time": self._end.text().strip() or None,
            "duration_minutes": int(self._mins.value()),
            "category": self._cat.currentText(),
            "days": days,
            "enabled": self._enabled.isChecked(),
        }

    def _load_form(self, routine: dict) -> None:
        self._editing_id = int(routine.get("id") or 0) or None
        self._title.setText(str(routine.get("title") or ""))
        self._start.setText(str(routine.get("start_time") or "09:00"))
        self._end.setText(str(routine.get("end_time") or "10:00"))
        self._mins.setValue(int(routine.get("duration_minutes") or 30))
        cat = str(routine.get("category") or "personal")
        if cat in _CATEGORIES:
            self._cat.setCurrentText(cat)
        self._enabled.setChecked(bool(routine.get("enabled", True)))
        days = set(routine.get("days") or ROUTINE_DAYS)
        for i, cb in enumerate(self._day_checks):
            cb.setChecked(ROUTINE_DAYS[i] in days)
        self._btn_save.setText("Update routine" if self._editing_id else "Save routine")

    def _clear_form(self) -> None:
        self._editing_id = None
        self._title.clear()
        self._start.setText("06:00")
        self._end.setText("06:30")
        self._mins.setValue(30)
        self._cat.setCurrentIndex(0)
        self._enabled.setChecked(True)
        for cb in self._day_checks:
            cb.setChecked(True)
        self._btn_save.setText("Save routine")

    def _save_inline(self) -> None:
        if not self._user_id:
            return
        try:
            if self._editing_id:
                update_routine(self._user_id, self._editing_id, self._payload())
                self._status.setText("Routine updated.")
            else:
                create_routine(self._user_id, self._payload())
                self._status.setText("Routine added.")
            self._clear_form()
            self.reload()
            self.changed.emit()
        except Exception as exc:  # noqa: BLE001
            self._status.setText(f"Save failed: {exc}")

    def _seed(self) -> None:
        if not self._user_id:
            return
        try:
            n = seed_routine_defaults(self._user_id)
            reorder_morning_routines(self._user_id)
            self._status.setText(f"Seeded {n} default(s) · times normalized.")
            self.reload()
            self.changed.emit()
        except Exception as exc:  # noqa: BLE001
            self._status.setText(str(exc))

    def _reorder(self) -> None:
        if not self._user_id:
            return
        try:
            n = reorder_morning_routines(self._user_id)
            self._status.setText(f"Morning-first order applied ({n} row(s) updated).")
            self.reload()
            self.changed.emit()
        except Exception as exc:  # noqa: BLE001
            self._status.setText(str(exc))

    def _apply(self) -> None:
        if not self._user_id:
            return
        try:
            r = apply_routines_today(self._user_id)
            self._status.setText(
                f"Added {r.get('created', 0)} block(s) for today (overlaps skipped — not carried from yesterday)."
            )
            self.changed.emit()
        except Exception as exc:  # noqa: BLE001
            self._status.setText(str(exc))

    def _move_row(self, index: int, delta: int) -> None:
        if not self._user_id or not self._row_ids:
            return
        j = index + delta
        if j < 0 or j >= len(self._row_ids):
            return
        ids = list(self._row_ids)
        ids[index], ids[j] = ids[j], ids[index]
        try:
            reorder_routine_ids(self._user_id, ids)
            self.reload()
            self.changed.emit()
        except Exception as exc:  # noqa: BLE001
            self._status.setText(str(exc))

    def _delete(self, routine_id: int) -> None:
        if not self._user_id:
            return
        try:
            delete_routine(self._user_id, routine_id)
            self._status.setText("Routine deleted.")
            self.reload()
            self.changed.emit()
        except Exception as exc:  # noqa: BLE001
            self._status.setText(str(exc))

    def has_routines(self) -> bool:
        return self._table.rowCount() > 0
