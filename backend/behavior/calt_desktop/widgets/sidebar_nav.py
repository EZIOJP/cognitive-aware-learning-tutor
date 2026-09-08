"""Left sidebar — collapsible stack control + tab navigation."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from backend.behavior.calt_desktop.desktop_prefs import (
    load_sidebar_collapsed,
    save_sidebar_collapsed,
)
from backend.behavior.calt_desktop.navigation import TAB_NAMES
from backend.behavior.calt_desktop.widgets.stack_control import StackControl

_EXPANDED_W = 196
_COLLAPSED_W = 56


class SidebarNav(QFrame):
    tab_selected = Signal(str)
    collapsed_changed = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sidebar")
        self._collapsed = load_sidebar_collapsed()

        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 12, 8, 12)
        lay.setSpacing(6)

        top = QHBoxLayout()
        self._brand = QLabel("CALT Desktop")
        self._brand.setObjectName("sidebarBrand")
        top.addWidget(self._brand, stretch=1)
        self._toggle = QPushButton("«")
        self._toggle.setObjectName("navChip")
        self._toggle.setFixedSize(28, 28)
        self._toggle.clicked.connect(self.toggle_collapsed)
        top.addWidget(self._toggle)
        lay.addLayout(top)

        self.stack_control = StackControl()
        lay.addWidget(self.stack_control)

        sep = QFrame()
        sep.setObjectName("sidebarSep")
        sep.setFixedHeight(1)
        lay.addWidget(sep)

        self._nav_label = QLabel("Navigate")
        self._nav_label.setObjectName("muted")
        lay.addWidget(self._nav_label)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: dict[str, QPushButton] = {}

        for name in TAB_NAMES:
            btn = QPushButton(name)
            btn.setObjectName("sidebarNav")
            btn.setCheckable(True)
            btn.setToolTip(name)
            btn.clicked.connect(lambda _c=False, n=name: self.tab_selected.emit(n))
            self._group.addButton(btn)
            self._buttons[name] = btn
            lay.addWidget(btn)

        lay.addStretch(1)

        self._hint = QLabel("Ctrl+1…9 · Ctrl+0")
        self._hint.setObjectName("muted")
        lay.addWidget(self._hint)

        self._apply_collapsed(self._collapsed, persist=False)

    def toggle_collapsed(self) -> None:
        self._apply_collapsed(not self._collapsed, persist=True)

    def _apply_collapsed(self, collapsed: bool, *, persist: bool) -> None:
        self._collapsed = collapsed
        self.setFixedWidth(_COLLAPSED_W if collapsed else _EXPANDED_W)
        self._toggle.setText("»" if collapsed else "«")
        self._brand.setVisible(not collapsed)
        self._nav_label.setVisible(not collapsed)
        self._hint.setVisible(not collapsed)
        self.stack_control.setVisible(not collapsed)
        for name, btn in self._buttons.items():
            if collapsed:
                btn.setText(name[:1])
            else:
                btn.setText(name)
        if persist:
            save_sidebar_collapsed(collapsed)
        self.collapsed_changed.emit(collapsed)

    def set_current_tab(self, name: str) -> None:
        btn = self._buttons.get(name)
        if btn is not None:
            btn.setChecked(True)
