"""Qt voice agent chat (preferred when CALT Desktop is running)."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from backend.behavior.voice_agent.agent import VoiceAgent

_window: QWidget | None = None
_lock = threading.Lock()


class VoiceChatWindow(QWidget):
    reply_ready = Signal(str)
    entry_enabled = Signal(bool)

    def __init__(self, agent: VoiceAgent, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._agent = agent
        self.setWindowTitle("CALT Voice Agent")
        self.resize(440, 520)
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowCloseButtonHint
            | Qt.WindowType.WindowMinimizeButtonHint
        )

        lay = QVBoxLayout(self)
        self._status = QLabel("Ctrl+Shift+Space for PTT · /brief · /voice jarvis|normal")
        self._status.setObjectName("muted")
        lay.addWidget(self._status)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        lay.addWidget(self._log, stretch=1)

        row = QHBoxLayout()
        self._entry = QLineEdit()
        self._entry.returnPressed.connect(self._send)
        row.addWidget(self._entry, stretch=1)
        btn_mic = QPushButton("Mic")
        btn_mic.clicked.connect(self._ptt)
        row.addWidget(btn_mic)
        btn_send = QPushButton("Send")
        btn_send.clicked.connect(self._send)
        row.addWidget(btn_send)
        lay.addLayout(row)

        self.reply_ready.connect(self._append_assistant)
        self.entry_enabled.connect(self._entry.setEnabled)
        self._agent.on_reply = lambda t: self.reply_ready.emit(t)

    def _append_user(self, text: str) -> None:
        self._log.append(f"You: {text}")

    def _append_assistant(self, text: str) -> None:
        self._log.append(f"Jarvis: {text}\n")

    def _send(self) -> None:
        text = self._entry.text().strip()
        if not text:
            return
        self._entry.clear()
        self._append_user(text)
        self._run_agent(text)

    def _ptt(self) -> None:
        self._status.setText("Listening…")
        try:
            from backend.behavior.voice_agent.io_speech import listen_once
            from backend.behavior.voice_agent.session import voice_session

            with voice_session(user_id=self._agent.user_id, trigger="chat_mic"):
                heard = listen_once()
        except Exception as exc:  # noqa: BLE001
            self._status.setText(str(exc))
            return
        self._status.setText("Ready")
        if heard:
            self._append_user(heard)
            self._run_agent(heard)
        else:
            self._log.append("Jarvis: I didn't catch that.\n")

    def _run_agent(self, text: str) -> None:
        self._entry.setEnabled(False)

        def work() -> None:
            try:
                self._agent.handle_utterance(text, say=True)
            except Exception as exc:  # noqa: BLE001
                self.reply_ready.emit(f"(error: {exc})")
            finally:
                self.entry_enabled.emit(True)

        threading.Thread(target=work, name="voice-chat-qt", daemon=True).start()


def open_voice_chat_qt(user_id: int) -> None:
    global _window
    from backend.behavior.voice_agent import get_agent, is_free_mode_paused

    if is_free_mode_paused():
        from PySide6.QtWidgets import QMessageBox

        QMessageBox.information(
            None,
            "Voice agent",
            "Paused in FREE mode — turns back on when you leave reward/free browsing.",
        )
        return

    with _lock:
        agent = get_agent(int(user_id))
        if _window is not None:
            try:
                _window.show()
                _window.raise_()
                _window.activateWindow()
                return
            except RuntimeError:
                _window = None
        _window = VoiceChatWindow(agent)
        _window.show()
