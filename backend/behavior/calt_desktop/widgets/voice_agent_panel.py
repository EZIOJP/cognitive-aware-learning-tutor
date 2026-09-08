"""Jarvis voice agent toggle + status for CALT Desktop."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QPushButton, QWidget

from backend.behavior.calt_desktop.theme import muted_label, primary_button
from backend.behavior.calt_desktop.widgets.gloss_panel import GlossPanel

if TYPE_CHECKING:
    from backend.behavior.tracker_service import TrackerService


def describe_voice_agent_ui(
    *,
    env_enabled: bool,
    free_paused: bool,
    hotkey_enabled: bool,
    hotkey_running: bool,
) -> tuple[str, bool, bool]:
    """Return (status_line, checkbox_checked, checkbox_enabled)."""
    if not env_enabled:
        return (
            "Disabled by VOICE_AGENT_ENABLED=0 (restart tracker after changing env).",
            False,
            False,
        )
    if free_paused:
        return (
            "Auto-paused in FREE mode (reward day / goal unlock) — frees VRAM for games.",
            False,
            False,
        )
    listen = "listening" if hotkey_running else "hotkey idle"
    if hotkey_enabled:
        return (f"ON · Ctrl+Shift+Space · {listen}", True, True)
    return ("OFF · tracker still runs; no mic until you turn this on", False, True)


class VoiceAgentPanel(GlossPanel):
    """Tray-equivalent voice hotkey toggle inside the desktop UI."""

    def __init__(self, service: TrackerService | None = None) -> None:
        super().__init__()
        self._service = service
        title = QLabel("Voice agent (Jarvis)")
        title.setObjectName("sectionTitle")
        self.body_layout().addWidget(title)

        self._status = QLabel("…")
        self._status.setWordWrap(True)
        self.body_layout().addWidget(self._status)

        row = QHBoxLayout()
        self._toggle = QCheckBox("Voice hotkey enabled")
        self._toggle.toggled.connect(self._on_toggle)
        row.addWidget(self._toggle)

        self._btn_chat = QPushButton("Open voice chat")
        self._btn_chat.clicked.connect(self._open_chat)
        row.addWidget(self._btn_chat)

        self._btn_voice_tab = primary_button("Voice clips tab")
        self._btn_voice_tab.clicked.connect(self._open_voice_tab)
        row.addWidget(self._btn_voice_tab)
        row.addStretch(1)
        self.body_layout().addLayout(row)

        self.body_layout().addWidget(
            muted_label(
                "PTT only — no wake word. Auto-pauses in FREE mode. "
                "Use OFF while gaming; tracker + gate keep running."
            )
        )

    def _uid(self) -> int:
        if self._service is None:
            return 0
        return int(getattr(self._service, "user_id", 0) or 0)

    def refresh(self) -> None:
        try:
            from backend.behavior.voice_agent import (
                is_free_mode_paused,
                is_voice_hotkey_enabled,
                is_voice_hotkey_running,
                voice_agent_enabled,
            )
        except Exception as exc:  # noqa: BLE001
            self._status.setText(str(exc))
            return

        env_on = voice_agent_enabled()
        free = is_free_mode_paused()
        hotkey_on = is_voice_hotkey_enabled()
        running = is_voice_hotkey_running()
        line, checked, enabled = describe_voice_agent_ui(
            env_enabled=env_on,
            free_paused=free,
            hotkey_enabled=hotkey_on,
            hotkey_running=running,
        )
        self._status.setText(line)
        self._toggle.blockSignals(True)
        self._toggle.setChecked(checked)
        self._toggle.setEnabled(enabled and self._uid() > 0)
        self._toggle.blockSignals(False)
        self._btn_chat.setEnabled(env_on and not free and self._uid() > 0)

    def _on_toggle(self, checked: bool) -> None:
        uid = self._uid()
        if not uid:
            return
        try:
            from backend.behavior.voice_agent import set_voice_hotkey_enabled

            set_voice_hotkey_enabled(checked, user_id=uid)
        except Exception as exc:  # noqa: BLE001
            self._status.setText(f"Toggle failed: {exc}")
        self.refresh()

    def _open_chat(self) -> None:
        uid = self._uid()
        if not uid:
            return
        try:
            from backend.behavior.voice_agent import open_voice_chat

            open_voice_chat(uid)
        except Exception as exc:  # noqa: BLE001
            self._status.setText(f"Chat failed: {exc}")

    def _open_voice_tab(self) -> None:
        from backend.behavior.calt_desktop.navigation import go_tab

        go_tab("Voice")
