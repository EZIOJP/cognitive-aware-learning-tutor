"""Voice session lifecycle — start → work → release (no always-on mic/models)."""

from __future__ import annotations

import logging
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator

log = logging.getLogger("desktop_tracker.voice_agent")

_lock = threading.Lock()
_active: "VoiceSession | None" = None


@dataclass
class VoiceSession:
    """One PTT/Mic turn (or short multi-turn confirm). Not a daemon."""

    session_id: str
    user_id: int | None = None
    started_at: float = field(default_factory=time.time)
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def elapsed_s(self) -> float:
        return max(0.0, time.time() - self.started_at)


def begin_session(*, user_id: int | None = None, **meta: Any) -> VoiceSession:
    """Mark session start. Does not open the mic by itself."""
    global _active
    session = VoiceSession(
        session_id=uuid.uuid4().hex[:12],
        user_id=user_id,
        meta=dict(meta),
    )
    with _lock:
        _active = session
    log.info(
        "voice session start id=%s user_id=%s meta=%s",
        session.session_id,
        user_id,
        meta or {},
    )
    return session


def get_active_session() -> VoiceSession | None:
    with _lock:
        return _active


def end_session(session: VoiceSession | None = None) -> None:
    """End session and release heavy resources (STT models, etc.)."""
    global _active
    with _lock:
        current = _active
        if session is not None and current is not None and current.session_id != session.session_id:
            # Stale end — still release resources once
            pass
        sid = (session or current).session_id if (session or current) else "?"
        elapsed = (session or current).elapsed_s if (session or current) else 0.0
        _active = None
    log.info("voice session end id=%s elapsed=%.2fs", sid, elapsed)
    release_session_resources()


def release_session_resources() -> None:
    """Unload session-scoped models. Safe to call when idle.

    Clears:
      - faster-whisper (if loaded this session)
    Does not touch:
      - pynput hotkey thread (CPU-only; stop via stop_hotkey / VOICE_AGENT_ENABLED)
      - unrelated Ollama/LM Studio sessions the user loaded outside voice
    Voice Ollama path uses keep_alive=0 (stream + task=voice_agent fallback).
    """
    try:
        from backend.behavior.voice_agent import io_speech

        io_speech.release_stt_models()
    except Exception as exc:  # noqa: BLE001
        log.debug("release_stt_models: %s", exc)


@contextmanager
def voice_session(*, user_id: int | None = None, **meta: Any) -> Iterator[VoiceSession]:
    """Context manager: begin → yield → end + release (always)."""
    session = begin_session(user_id=user_id, **meta)
    try:
        yield session
    finally:
        end_session(session)
