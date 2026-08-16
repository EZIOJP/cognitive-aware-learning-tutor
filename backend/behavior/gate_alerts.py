"""Rate-limited spoken gate alerts — canned lines only (no LLM / no GPU).

Extensions POST /api/behavior/gate-alert → queue file.
Desktop tracker drains queue + speaks via ephemeral edge-tts / Piper / SAPI.

Dialogue source: ``voice_agent.block_dialogues`` (expandable pools).

Audio: one utterance at a time (in-process queue + cross-process file lock).
"""

from __future__ import annotations

import json
import logging
import os
import queue
import threading
import time
from pathlib import Path
from typing import Any

log = logging.getLogger("calt.gate_alerts")

_ROOT = Path(__file__).resolve().parent.parent.parent
_QUEUE_PATH = _ROOT / "data" / "behavior" / "pending_gate_alerts.json"
_TTS_BUSY_PATH = _ROOT / "data" / "behavior" / "tts_busy.lock"
_lock = threading.Lock()
_last_speak_at = 0.0
_last_text_norm = ""
_DEFAULT_GAP_S = 45.0

# Single FIFO worker — never start overlapping speak threads
_speak_q: queue.Queue[tuple[str, threading.Event | None] | None] = queue.Queue()
_worker_started = False
_worker_lock = threading.Lock()
_speaking = False


def speak_gap_s() -> float:
    try:
        v = float(os.environ.get("GATE_ALERT_SPEAK_GAP_S") or _DEFAULT_GAP_S)
    except ValueError:
        v = _DEFAULT_GAP_S
    return max(15.0, min(120.0, v))


def line_for(kind: str, *, detail: str = "") -> str:
    """Pick a canned Jarvis line for this event. Ignores detail for speak text."""
    _ = detail
    from backend.behavior.voice_agent.block_dialogues import pick_dialogue

    return pick_dialogue(kind, mode="random")


def enqueue_alert(kind: str, *, detail: str = "", message: str | None = None) -> dict[str, Any]:
    """Append a pending alert for the desktop tracker to speak (and soft-lock).

    If ``message`` is provided it is used as-is (escape hatch / tests only).
    Default path always uses canned ``line_for(kind)`` — never LLM.
    """
    text = (message if message is not None else line_for(kind, detail=detail)).strip()
    item = {
        "kind": (kind or "default").strip().lower(),
        "detail": (detail or "")[:120],
        "message": text[:240],
        "ts": time.time(),
        "canned": message is None,
    }
    with _lock:
        _QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
        items: list[dict[str, Any]] = []
        if _QUEUE_PATH.is_file():
            try:
                raw = json.loads(_QUEUE_PATH.read_text(encoding="utf-8"))
                if isinstance(raw, list):
                    items = [x for x in raw if isinstance(x, dict)]
            except Exception:  # noqa: BLE001
                items = []
        items.append(item)
        items = items[-20:]
        _QUEUE_PATH.write_text(json.dumps(items, indent=0), encoding="utf-8")
    return item


def drain_alerts(*, max_age_s: float = 120.0) -> list[dict[str, Any]]:
    """Pop pending alerts (tracker side). Drops stale entries."""
    with _lock:
        if not _QUEUE_PATH.is_file():
            return []
        try:
            raw = json.loads(_QUEUE_PATH.read_text(encoding="utf-8"))
            items = [x for x in raw if isinstance(x, dict)] if isinstance(raw, list) else []
        except Exception:  # noqa: BLE001
            items = []
        try:
            _QUEUE_PATH.write_text("[]", encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass
    now = time.time()
    return [x for x in items if (now - float(x.get("ts") or 0)) <= max_age_s]


def is_speaking() -> bool:
    """True if this process is mid-utterance or another process holds the TTS lock."""
    if _speaking:
        return True
    return _cross_process_busy()


def _cross_process_busy() -> bool:
    try:
        if not _TTS_BUSY_PATH.is_file():
            return False
        age = time.time() - _TTS_BUSY_PATH.stat().st_mtime
        # Stale lock after crash — allow after 3 minutes
        if age > 180.0:
            try:
                _TTS_BUSY_PATH.unlink(missing_ok=True)
            except OSError:
                pass
            return False
        return True
    except OSError:
        return False


def _acquire_cross_process(*, wait_s: float = 90.0) -> bool:
    """Exclusive TTS lock across API + tracker processes. Returns False if timed out."""
    deadline = time.time() + max(0.5, wait_s)
    _TTS_BUSY_PATH.parent.mkdir(parents=True, exist_ok=True)
    while time.time() < deadline:
        try:
            # O_EXCL create — atomic on Windows for new files
            fd = os.open(str(_TTS_BUSY_PATH), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            try:
                os.write(fd, f"{os.getpid()}\n{time.time()}\n".encode("utf-8"))
            finally:
                os.close(fd)
            return True
        except FileExistsError:
            if not _cross_process_busy():
                continue
            time.sleep(0.15)
        except OSError:
            time.sleep(0.15)
    return False


def _release_cross_process() -> None:
    try:
        _TTS_BUSY_PATH.unlink(missing_ok=True)
    except OSError:
        pass


def _ensure_worker() -> None:
    global _worker_started
    with _worker_lock:
        if _worker_started:
            return
        t = threading.Thread(target=_speak_worker, name="gate-speak-worker", daemon=True)
        t.start()
        _worker_started = True


def _speak_worker() -> None:
    global _speaking, _last_speak_at
    while True:
        item = _speak_q.get()
        if item is None:
            continue
        text, done_ev = item
        text = (text or "").strip()
        if not text:
            if done_ev is not None:
                done_ev.set()
            continue
        got = _acquire_cross_process(wait_s=90.0)
        if not got:
            log.warning("speak skipped — could not acquire TTS lock")
            if done_ev is not None:
                done_ev.set()
            continue
        _speaking = True
        try:
            from backend.behavior.voice_agent.io_speech import speak

            speak(text[:280])
            _last_speak_at = time.time()
        except Exception as exc:  # noqa: BLE001
            log.warning("speak_alert failed: %s", exc)
        finally:
            _speaking = False
            _release_cross_process()
            if done_ev is not None:
                done_ev.set()


def speak_alert(
    text: str,
    *,
    force: bool = False,
    skip_if_busy: bool = False,
) -> bool:
    """Enqueue a short canned line for the single TTS worker. Returns True if queued.

    Rate-limited unless ``force``. Never starts a second overlapping audio stream —
    utterances play FIFO. ``skip_if_busy`` drops the line if audio is already playing
    (used when API already spoke and tracker would duplicate).
    """
    global _last_speak_at, _last_text_norm
    text = (text or "").strip()
    if not text:
        return False
    try:
        from backend.behavior.voice_agent import voice_runtime_allowed

        if not voice_runtime_allowed():
            log.debug("speak_alert skipped — voice/gaming silence")
            return False
    except Exception:  # noqa: BLE001
        pass

    if skip_if_busy and (is_speaking() or _speak_q.qsize() > 0):
        log.debug("speak_alert skipped — already speaking/queued")
        return False

    now = time.time()
    gap = speak_gap_s()
    norm = " ".join(text.lower().split())
    with _lock:
        if not force:
            if (now - _last_speak_at) < gap:
                log.debug("speak_alert rate-limited (%.0fs gap)", gap)
                return False
            if norm and norm == _last_text_norm and (now - _last_speak_at) < gap:
                log.debug("speak_alert deduped identical line")
                return False
        # Reserve slot immediately so parallel force=True callers still serialize via queue
        # but don't stampede rate-limit on drain duplicates within same second.
        _last_speak_at = now
        _last_text_norm = norm

    _ensure_worker()
    try:
        from backend.behavior.voice_agent.announce import surface_dialogue

        surface_dialogue(text[:280], source="speak_alert")
    except Exception:  # noqa: BLE001
        pass
    _speak_q.put((text[:280], None))
    return True


def speak_alert_sync(text: str, *, force: bool = False) -> bool:
    """Queue and wait until this utterance finishes (for morning brief sequences)."""
    global _last_speak_at, _last_text_norm
    text = (text or "").strip()
    if not text:
        return False
    try:
        from backend.behavior.voice_agent import voice_runtime_allowed

        if not voice_runtime_allowed():
            return False
    except Exception:  # noqa: BLE001
        pass

    now = time.time()
    gap = speak_gap_s()
    norm = " ".join(text.lower().split())
    with _lock:
        if not force and (now - _last_speak_at) < gap:
            return False
        _last_speak_at = now
        _last_text_norm = norm

    done = threading.Event()
    _ensure_worker()
    try:
        from backend.behavior.voice_agent.announce import surface_dialogue

        surface_dialogue(text[:280], source="speak_alert_sync")
    except Exception:  # noqa: BLE001
        pass
    _speak_q.put((text[:280], done))
    return done.wait(timeout=120.0)


def notify_block(kind: str, *, detail: str = "", message: str | None = None) -> dict[str, Any]:
    """Enqueue for tracker soft-lock + speak. Does not speak in the API process.

    Speaking is the tracker's job (drain_alerts) so we never get API Edge + tracker
    SAPI overlapping on the same alert.
    """
    return enqueue_alert(kind, detail=detail, message=message)


def reset_speak_state_for_tests() -> None:
    global _last_speak_at, _last_text_norm, _speaking
    _last_speak_at = 0.0
    _last_text_norm = ""
    _speaking = False
    # Drain pending queue without speaking
    try:
        while True:
            _speak_q.get_nowait()
    except queue.Empty:
        pass
    with _lock:
        try:
            if _QUEUE_PATH.is_file():
                _QUEUE_PATH.write_text("[]", encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass
    _release_cross_process()
