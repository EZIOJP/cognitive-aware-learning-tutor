"""Pending OPEN/FOCUS command for SelfTracker (one CALT tab discipline).

Tracker writes; extension polls GET and clears. Survives brief API blips via file.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any

from backend.paths import ROOT

_PATH = ROOT / "data" / "browser_calt_tab_command.json"
_lock = threading.Lock()
_OPEN_DEBOUNCE_S = 15.0
_last_open_key = ""
_last_open_at = 0.0


def _load() -> dict[str, Any]:
    if not _PATH.is_file():
        return {}
    try:
        raw = json.loads(_PATH.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save(data: dict[str, Any]) -> None:
    _PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = _PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=0), encoding="utf-8")
    tmp.replace(_PATH)


def request_focus(path_or_url: str, *, force: bool = False) -> dict[str, Any]:
    """Queue a focus/open for the extension. Debounced unless *force*."""
    global _last_open_key, _last_open_at
    path = (path_or_url or "/").strip() or "/"
    now = time.time()
    with _lock:
        if not force and path == _last_open_key and (now - _last_open_at) < _OPEN_DEBOUNCE_S:
            return {"ok": True, "queued": False, "reason": "debounced", "path": path}
        _last_open_key = path
        _last_open_at = now
        _save(
            {
                "action": "open_path",
                "path": path,
                "ts": now,
                "id": f"{int(now * 1000)}",
            }
        )
        return {"ok": True, "queued": True, "path": path}


def peek_command() -> dict[str, Any] | None:
    with _lock:
        data = _load()
        if not data.get("action"):
            return None
        # Expire after 60s
        ts = float(data.get("ts") or 0)
        if ts and time.time() - ts > 60:
            _save({})
            return None
        return dict(data)


def consume_command() -> dict[str, Any] | None:
    with _lock:
        data = _load()
        if not data.get("action"):
            return None
        _save({})
        return dict(data)


def last_jarvis_line_payload() -> dict[str, Any]:
    """Latest canned/LLM line for extension popup."""
    try:
        from backend.behavior.voice_agent import announce

        text = announce.last_jarvis_line(max_age_s=3600.0) or ""
        return {"text": text[:240], "ts": time.time() if text else 0}
    except Exception:
        return {"text": "", "ts": 0}
