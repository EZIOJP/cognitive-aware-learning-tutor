"""Tracker-native CALT voice agent.

Hotkey-only PTT (Ctrl+Shift+Space) — no wake word / always-on mic.
Session lifecycle: begin → STT/LLM/TTS → release (see session.py).

Idle (tracker up, no PTT/chat session):
  - No Whisper / Kokoro / TTS engines resident
  - No mic capture loop
  - Optional pynput hotkey listener only (CPU-near-zero) unless disabled
  - Ollama voice path uses keep_alive=0 (does not unload unrelated Ollama sessions)

Disable for gaming: VOICE_AGENT_ENABLED=0, tray → Voice hotkey OFF, or automatic
pause while browser gate is FREE (reward day / goal unlock / free override).
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Any

log = logging.getLogger("desktop_tracker.voice_agent")

_agent = None
_agent_lock = threading.Lock()
_hotkey_stop: threading.Event | None = None
# None = follow VOICE_AGENT_ENABLED; True/False = tray override for this process
_hotkey_runtime: bool | None = None
# Auto-paused while FREE so games get VRAM/CPU/GPU back
_free_mode_paused: bool = False


def voice_agent_enabled() -> bool:
    """Env kill-switch: VOICE_AGENT_ENABLED=0|false|off|no → fully skip auto-start/hotkey."""
    raw = (os.environ.get("VOICE_AGENT_ENABLED") or "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def is_free_mode_paused() -> bool:
    return bool(_free_mode_paused)


def voice_runtime_allowed() -> bool:
    """False when env-off, tray-off, or FREE-mode auto-pause (gaming VRAM)."""
    if not voice_agent_enabled():
        return False
    if _free_mode_paused:
        return False
    if _hotkey_runtime is False:
        return False
    return True


def gate_is_free_mode(gate: dict[str, Any] | None) -> bool:
    """True when distraction gate grants all-day / override FREE browsing."""
    if not isinstance(gate, dict):
        return False
    if gate.get("reward_day") or gate.get("day_unlimited"):
        return True
    browser = gate.get("browser") if isinstance(gate.get("browser"), dict) else {}
    mode = str(browser.get("mode") or gate.get("browser_mode") or "").strip().lower()
    if mode == "free":
        return True
    if browser.get("free_override_active"):
        return True
    return False


def sync_voice_with_browser_gate(
    gate: dict[str, Any] | None,
    *,
    user_id: int | None = None,
) -> dict[str, Any]:
    """Pause voice (hotkey + models) in FREE mode; restore when leaving FREE.

    Does not override an explicit tray OFF — after FREE ends, hotkey stays off
    until the user turns it back on.
    """
    global _free_mode_paused
    want_pause = gate_is_free_mode(gate)
    if want_pause and not _free_mode_paused:
        _free_mode_paused = True
        stop_voice_agent()
        log.info("Voice agent paused (FREE mode) — VRAM/CPU freed for games")
        return {"paused": True, "changed": True, "reason": "free_mode"}
    if want_pause and _free_mode_paused:
        return {"paused": True, "changed": False, "reason": "free_mode"}
    if not want_pause and _free_mode_paused:
        _free_mode_paused = False
        # Respect tray OFF; otherwise bring hotkey back.
        if voice_agent_enabled() and _hotkey_runtime is not False and user_id is not None:
            start_voice_agent(int(user_id), enable_hotkey=True)
        log.info("Voice agent resumed (left FREE mode)")
        return {"paused": False, "changed": True, "reason": "left_free"}
    return {"paused": False, "changed": False, "reason": "study_or_armed"}


def is_voice_hotkey_enabled() -> bool:
    """Whether the PTT hotkey should be (or stay) registered."""
    if not voice_agent_enabled():
        return False
    if _free_mode_paused:
        return False
    if _hotkey_runtime is not None:
        return _hotkey_runtime
    return True


def is_voice_hotkey_running() -> bool:
    return _hotkey_stop is not None and not _hotkey_stop.is_set()


def set_voice_hotkey_enabled(enabled: bool, *, user_id: int | None = None) -> bool:
    """Tray/runtime toggle: stop or start PTT listener. Releases STT on disable."""
    global _hotkey_runtime
    if enabled and _free_mode_paused:
        log.info("Voice hotkey stays OFF during FREE mode (gaming VRAM)")
        return False
    _hotkey_runtime = bool(enabled)
    if not enabled:
        stop_hotkey()
        try:
            from backend.behavior.voice_agent.session import release_session_resources

            release_session_resources()
        except Exception as exc:  # noqa: BLE001
            log.debug("release on hotkey disable: %s", exc)
        log.info("Voice hotkey OFF (gaming-safe; tracker still runs)")
        return False
    if user_id is not None:
        start_voice_agent(int(user_id), enable_hotkey=True)
    log.info("Voice hotkey ON")
    return True


def get_agent(user_id: int):
    global _agent
    from backend.behavior.voice_agent.agent import VoiceAgent

    with _agent_lock:
        if _agent is None or getattr(_agent, "user_id", None) != int(user_id):
            _agent = VoiceAgent(user_id)
        return _agent


def start_voice_agent(user_id: int, *, enable_hotkey: bool = True) -> Any:
    """Idempotent: ensure agent exists; optionally register PTT hotkey.

    Does **not** preload Whisper, TTS, or LLM — those load only inside a session.
    """
    if _free_mode_paused:
        log.info("Voice agent start skipped — FREE mode pause (gaming)")
        return None
    agent = get_agent(user_id)
    want = bool(enable_hotkey) and is_voice_hotkey_enabled()
    if want:
        _ensure_hotkey(agent)
    else:
        stop_hotkey()
        log.info(
            "Voice agent ready for user_id=%s (hotkey disabled; no models loaded)",
            user_id,
        )
        return agent
    log.info("Voice agent ready for user_id=%s (hotkey-only; no wake word)", user_id)
    return agent


def open_voice_chat(user_id: int) -> None:
    """Open chat UI. Does not force-enable hotkey if user disabled it for gaming."""
    if _free_mode_paused:
        log.info("Voice chat blocked during FREE mode (gaming VRAM)")
        try:
            import tkinter as tk
            from tkinter import messagebox

            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            messagebox.showinfo(
                "Voice agent",
                "Voice agent is paused in FREE mode so games can use VRAM/CPU/GPU.\n"
                "It turns back on when you leave free / reward day.",
                parent=root,
            )
            root.destroy()
        except Exception:  # noqa: BLE001
            pass
        return
    agent = start_voice_agent(user_id, enable_hotkey=is_voice_hotkey_enabled())
    if agent is None:
        return
    try:
        from backend.behavior.voice_agent.morning_brief import maybe_chat_open_greet

        maybe_chat_open_greet(int(user_id))
    except Exception as exc:  # noqa: BLE001
        log.debug("chat-open greet skipped: %s", exc)
    from backend.behavior.voice_agent.chat_ui import open_chat_window

    open_chat_window(agent)


def stop_hotkey() -> None:
    """Stop pynput listener only (CPU-only idle path)."""
    global _hotkey_stop
    if _hotkey_stop is not None:
        _hotkey_stop.set()
        _hotkey_stop = None


def stop_voice_agent() -> None:
    """Stop hotkey listener, clear agent, release session resources."""
    global _agent
    stop_hotkey()
    with _agent_lock:
        _agent = None
    try:
        from backend.behavior.voice_agent.session import release_session_resources

        release_session_resources()
    except Exception as exc:  # noqa: BLE001
        log.debug("release on stop: %s", exc)


def _ensure_hotkey(agent) -> None:
    global _hotkey_stop
    if not is_voice_hotkey_enabled():
        return
    if _hotkey_stop is not None and not _hotkey_stop.is_set():
        return
    try:
        from pynput import keyboard
    except ImportError:
        log.info("pynput not installed — voice agent hotkey disabled (use chat Mic/Send)")
        return

    stop = threading.Event()
    _hotkey_stop = stop

    # Ctrl+Shift+Space — not a wake word; mic opens only inside the session below
    combo = {keyboard.Key.ctrl_l, keyboard.Key.shift, keyboard.Key.space}
    combo2 = {keyboard.Key.ctrl_r, keyboard.Key.shift, keyboard.Key.space}
    current: set = set()

    def on_press(key) -> None:
        if stop.is_set():
            return False
        current.add(key)
        if combo.issubset(current) or combo2.issubset(current):
            current.clear()

            def work() -> None:
                from backend.behavior.voice_agent.io_speech import listen_once, speak
                from backend.behavior.voice_agent.session import voice_session

                with voice_session(user_id=agent.user_id, trigger="hotkey"):
                    speak("Listening")
                    heard = listen_once()
                    if heard:
                        agent.handle_utterance(heard, say=True)
                    else:
                        speak("I didn't catch that")

            threading.Thread(target=work, name="voice-ptt", daemon=True).start()
        return None

    def on_release(key) -> None:
        current.discard(key)
        if stop.is_set():
            return False
        return None

    def run() -> None:
        with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
            stop.wait()
            listener.stop()

    threading.Thread(target=run, name="voice-hotkey", daemon=True).start()
    log.info("Voice agent hotkey: Ctrl+Shift+Space (CPU-only listener; no mic until PTT)")
