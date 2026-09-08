"""Dark glossy Qt theme aligned with web gloss-panel / slate palette."""

from __future__ import annotations

from PySide6.QtWidgets import QPushButton, QWidget

CALT_STYLESHEET = """
QMainWindow, QWidget {
  background-color: #0f172a;
  color: #e2e8f0;
  font-family: "Segoe UI", system-ui, sans-serif;
  font-size: 13px;
}
QTabWidget::pane {
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  background: rgba(15, 23, 42, 0.95);
  top: -1px;
}
QTabBar::tab {
  background: rgba(30, 41, 59, 0.85);
  color: #94a3b8;
  padding: 8px 14px;
  margin-right: 3px;
  border-top-left-radius: 8px;
  border-top-right-radius: 8px;
}
QTabBar::tab:selected {
  background: rgba(16, 185, 129, 0.22);
  color: #ecfdf5;
  border-bottom: 2px solid #10b981;
}
QPushButton {
  background: rgba(30, 41, 59, 0.92);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 8px;
  padding: 8px 14px;
  color: #e2e8f0;
}
QPushButton:hover {
  background: rgba(51, 65, 85, 0.95);
  border-color: rgba(255, 255, 255, 0.2);
}
QPushButton:disabled {
  color: #64748b;
  background: rgba(30, 41, 59, 0.55);
}
QPushButton#primary {
  background: rgba(5, 150, 105, 0.78);
  border-color: rgba(16, 185, 129, 0.45);
  color: #ecfdf5;
  font-weight: 600;
}
QPushButton#primary:hover {
  background: rgba(5, 150, 105, 0.95);
}
QPushButton#primary:disabled {
  background: rgba(30, 41, 59, 0.6);
  color: #64748b;
}
QPushButton#navChip {
  background: rgba(30, 41, 59, 0.65);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 999px;
  padding: 5px 12px;
  font-size: 12px;
  color: #cbd5e1;
}
QPushButton#navChip:hover {
  background: rgba(51, 65, 85, 0.9);
  border-color: rgba(16, 185, 129, 0.35);
  color: #ecfdf5;
}
QFrame#sidebar {
  background: rgba(15, 23, 42, 0.98);
  border-right: 1px solid rgba(255, 255, 255, 0.08);
}
QLabel#sidebarBrand {
  font-size: 14px;
  font-weight: 700;
  color: #f8fafc;
  padding: 2px 4px 6px 4px;
}
QFrame#sidebarSep {
  background: rgba(255, 255, 255, 0.08);
  margin: 4px 0 8px 0;
}
QPushButton#sidebarNav {
  text-align: left;
  padding: 9px 12px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: #94a3b8;
}
QPushButton#sidebarNav:hover {
  background: rgba(51, 65, 85, 0.55);
  color: #e2e8f0;
}
QPushButton#sidebarNav:checked {
  background: rgba(16, 185, 129, 0.2);
  color: #ecfdf5;
  font-weight: 600;
  border-left: 3px solid #10b981;
  padding-left: 9px;
}
QPushButton#stackControl {
  text-align: left;
  padding: 10px 12px;
  border-radius: 10px;
  font-size: 12px;
  line-height: 1.35;
}
QPushButton#stackControl[stackState="down"] {
  background: rgba(127, 29, 29, 0.35);
  border: 1px solid rgba(248, 113, 113, 0.35);
  color: #fecaca;
}
QPushButton#stackControl[stackState="partial"] {
  background: rgba(120, 53, 15, 0.35);
  border: 1px solid rgba(251, 191, 36, 0.35);
  color: #fde68a;
}
QPushButton#stackControl[stackState="up"] {
  background: rgba(5, 150, 105, 0.28);
  border: 1px solid rgba(16, 185, 129, 0.45);
  color: #d1fae5;
  font-weight: 600;
}
QPushButton#stackControl[stackState="starting"] {
  background: rgba(30, 58, 138, 0.35);
  border: 1px solid rgba(96, 165, 250, 0.35);
  color: #bfdbfe;
}
QPushButton#stepRail {
  background: rgba(30, 41, 59, 0.7);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px;
  padding: 6px 10px;
  font-size: 12px;
}
QPushButton#stepRail:checked {
  background: rgba(16, 185, 129, 0.28);
  border-color: rgba(16, 185, 129, 0.5);
  color: #ecfdf5;
  font-weight: 600;
}
QProgressBar {
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 6px;
  height: 14px;
  text-align: center;
  color: #e2e8f0;
}
QProgressBar::chunk {
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
    stop:0 #059669, stop:1 #34d399);
  border-radius: 5px;
}
QFrame#glossPanel {
  background: rgba(15, 23, 42, 0.88);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
}
QFrame#floatingDetail {
  background: rgba(30, 41, 59, 0.96);
  border: 1px solid rgba(16, 185, 129, 0.35);
  border-radius: 12px;
}
QLabel#sectionTitle {
  font-size: 15px;
  font-weight: 600;
  color: #f8fafc;
}
QLabel#muted {
  color: #94a3b8;
  font-size: 12px;
}
QLabel#hero {
  font-size: 22px;
  font-weight: 700;
  color: #f8fafc;
}
QLabel#stackUp {
  color: #6ee7b7;
}
QLabel#stackDown {
  color: #fca5a5;
}
QLineEdit, QPlainTextEdit, QSpinBox, QComboBox, QTextBrowser {
  background: rgba(15, 23, 42, 0.75);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 8px;
  padding: 6px 8px;
  color: #e2e8f0;
  selection-background-color: rgba(16, 185, 129, 0.35);
}
QCheckBox {
  spacing: 8px;
}
QCheckBox::indicator {
  width: 16px;
  height: 16px;
  border-radius: 4px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  background: rgba(15, 23, 42, 0.8);
}
QCheckBox::indicator:checked {
  background: rgba(16, 185, 129, 0.75);
  border-color: #10b981;
}
QTableWidget, QListWidget {
  background: rgba(15, 23, 42, 0.65);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 10px;
  gridline-color: rgba(255, 255, 255, 0.06);
}
QHeaderView::section {
  background: rgba(30, 41, 59, 0.9);
  color: #cbd5e1;
  padding: 6px;
  border: none;
}
QScrollBar:vertical {
  background: transparent;
  width: 10px;
}
QScrollBar::handle:vertical {
  background: rgba(148, 163, 184, 0.35);
  border-radius: 5px;
  min-height: 24px;
}
"""


def apply_calt_theme(widget: QWidget) -> None:
    widget.setStyleSheet(CALT_STYLESHEET)


def primary_button(text: str, parent: QWidget | None = None) -> QPushButton:
    btn = QPushButton(text, parent)
    btn.setObjectName("primary")
    return btn


def muted_label(text: str, parent: QWidget | None = None):
    from PySide6.QtWidgets import QLabel

    lab = QLabel(text, parent)
    lab.setObjectName("muted")
    lab.setWordWrap(True)
    return lab
