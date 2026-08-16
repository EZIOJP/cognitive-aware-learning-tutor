"""Surface canned Jarvis dialogue as text (chat UI + history + Today’s rules).

TTS stays in ``gate_alerts.speak_alert`` — this module only shows text once.
Works across API ↔ tracker via a small JSON feed under ``data/voice_agent/``.
"""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable

from backend.paths import ROOT

log = logging.getLogger("calt.voice_announce")

_FEED_PATH = ROOT / "data" / "voice_agent" / "dialogue_feed.json"
_MAX_LINES = 40
_lock = threading.Lock()
_ui_callback: Callable[[str], None] | None = None
_seen_ids: set[str] = set()
_last_seen_seq = 0


def _empty() -> dict[str, Any]:
    return {"seq": 0, "lines": []}


def _load() -> dict[str, Any]:
    if not _FEED_PATH.is_file():
        return _empty()
    try:
        raw = json.loads(_FEED_PATH.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return _empty()
        lines = raw.get("lines") if isinstance(raw.get("lines"), list) else []
        seq = int(raw.get("seq") or 0)
        return {"seq": seq, "lines": [x for x in lines if isinstance(x, dict)]}
    except Exception:  # noqa: BLE001
        return _empty()


def _save(data: dict[str, Any]) -> None:
    _FEED_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = _FEED_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=0), encoding="utf-8")
    tmp.replace(_FEED_PATH)


def register_ui_callback(cb: Callable[[str], None] | None) -> None:
    """Chat window registers an append-Agent callback; clear on close."""
    global _ui_callback
    with _lock:
        _ui_callback = cb


def surface_dialogue(text: str, *, source: str = "canned") -> str | None:
    """Record a spoken line for UI. Returns line id or None if empty/dup.

    Does not TTS. Call before or when queuing speak_alert.
    """
    text = (text or "").strip()
    if not text:
        return None
    text = text[:400]
    entry_id = uuid.uuid4().hex[:12]
    now = time.time()
    cb: Callable[[str], None] | None = None
    with _lock:
        data = _load()
        lines = list(data.get("lines") or [])
        # Dedupe identical line within 2s (force double-queue)
        if lines:
            last = lines[-1]
            if (
                str(last.get("text") or "").strip() == text
                and (now - float(last.get("ts") or 0)) < 2.0
            ):
                return None
        seq = int(data.get("seq") or 0) + 1
        entry = {
            "id": entry_id,
            "text": text,
            "ts": now,
            "source": (source or "canned")[:40],
            "seq": seq,
        }
        lines.append(entry)
        lines = lines[-_MAX_LINES:]
        _save({"seq": seq, "lines": lines})
        _seen_ids.add(entry_id)
        # Cap seen set
        if len(_seen_ids) > 200:
            _seen_ids.clear()
            _seen_ids.update(x.get("id") for x in lines if x.get("id"))
        cb = _ui_callback
    if cb is not None:
        try:
            cb(text)
        except Exception as exc:  # noqa: BLE001
            log.debug("ui callback failed: %s", exc)
    try:
        from backend.behavior.voice_agent.jarvis_toast import show_jarvis_toast

        show_jarvis_toast(text)
    except Exception as exc:  # noqa: BLE001
        log.debug("jarvis toast failed: %s", exc)
    return entry_id


def last_jarvis_line(*, max_age_s: float = 600.0) -> str | None:
    """Most recent canned line for Today’s rules tip (if fresh)."""
    with _lock:
        data = _load()
        lines = data.get("lines") or []
        if not lines:
            return None
        last = lines[-1]
        text = str(last.get("text") or "").strip()
        if not text:
            return None
        age = time.time() - float(last.get("ts") or 0)
        if age > max_age_s:
            return None
        return text if len(text) <= 120 else text[:117] + "…"


def pending_lines_for_ui(*, since_seq: int = 0) -> list[dict[str, Any]]:
    """Lines with seq > since_seq (for chat poller / reopen flush)."""
    with _lock:
        data = _load()
        out = []
        for row in data.get("lines") or []:
            try:
                s = int(row.get("seq") or 0)
            except (TypeError, ValueError):
                continue
            if s > since_seq:
                out.append(row)
        return out


def feed_seq() -> int:
    with _lock:
        return int(_load().get("seq") or 0)


def recent_lines(*, limit: int = 12) -> list[str]:
    with _lock:
        lines = _load().get("lines") or []
        return [str(x.get("text") or "") for x in lines[-limit:] if x.get("text")]


def reset_for_tests() -> None:
    global _ui_callback, _last_seen_seq
    with _lock:
        _ui_callback = None
        _seen_ids.clear()
        _last_seen_seq = 0
        try:
            if _FEED_PATH.is_file():
                _FEED_PATH.unlink()
        except OSError:
            pass
