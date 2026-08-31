"""Settings tab — stack health, Jarvis, launch hints."""

from __future__ import annotations

import os
import webbrowser

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from backend.behavior.calt_desktop.constants import CALENDAR_URL, LOGIN_URL, STUDY_URL


class SettingsTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Settings"))
        self._stack = QLabel("Stack: …")
        self._stack.setWordWrap(True)
        lay.addWidget(self._stack)
        self._env = QLabel("")
        self._env.setWordWrap(True)
        self._env.setStyleSheet("color: #94a3b8;")
        lay.addWidget(self._env)

        btn_study = QPushButton("Open study app")
        btn_study.clicked.connect(lambda: webbrowser.open(STUDY_URL))
        btn_cal = QPushButton("Open calendar (web)")
        btn_cal.clicked.connect(lambda: webbrowser.open(CALENDAR_URL))
        btn_login = QPushButton("Open login")
        btn_login.clicked.connect(lambda: webbrowser.open(LOGIN_URL))
        for b in (btn_study, btn_cal, btn_login):
            lay.addWidget(b)

        tip = QLabel(
            "Jarvis / voice agent runs inside this process with the tracker.\n"
            "FREE mode pauses voice to free VRAM. Hotkey: Ctrl+Shift+Space (if pynput installed).\n"
            "TTS: pip install edge-tts for neural voice; else Piper/SAPI.\n"
            "Planning calendar grid stays on the website — this app owns rules & watch/voice."
        )
        tip.setWordWrap(True)
        tip.setStyleSheet("color: #94a3b8;")
        lay.addWidget(tip)
        lay.addStretch(1)

        self._timer = QTimer(self)
        self._timer.setInterval(8000)
        self._timer.timeout.connect(self.refresh)
        self._timer.start()
        self.refresh()

    def refresh(self) -> None:
        try:
            from backend.behavior.stack_health import get_stack_health

            self._stack.setText(get_stack_health().status_line())
        except Exception as exc:  # noqa: BLE001
            self._stack.setText(f"Stack: {exc}")
        self._env.setText(
            f"CALT_DESKTOP={os.environ.get('CALT_DESKTOP', '')} · "
            f"TRACKER_NO_TRAY={os.environ.get('TRACKER_NO_TRAY', '')} · "
            f"pid={os.getpid()}"
        )
