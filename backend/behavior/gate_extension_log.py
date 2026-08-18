"""Append-only log for CALT Gate extension redirects (Edge crash diagnostics)."""

from __future__ import annotations

import json
import logging
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.paths import ROOT

log = logging.getLogger("calt.gate_extension")
_LOG_PATH = ROOT / "data" / "logs" / "gate_extension.log"
_lock = threading.Lock()


def append_gate_extension_event(body: dict[str, Any]) -> Path:
    """Write one JSON line and optionally enqueue a desktop notice."""
    _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": datetime.now(UTC).isoformat(),
        "event": str(body.get("event") or "unknown")[:40],
        "source": str(body.get("source") or "calt-gate")[:40],
        "kind": str(body.get("kind") or "")[:60],
        "detail": str(body.get("detail") or "")[:200],
        "url": str(body.get("url") or "")[:400],
        "target": str(body.get("target") or "")[:400],
        "tab_id": body.get("tab_id"),
        "notify": bool(body.get("notify")),
    }
    line = json.dumps(row, ensure_ascii=False)
    with _lock:
        with _LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    log.info(
        "gate_extension %s %s",
        row["event"],
        (row["detail"] or row["url"] or "")[:80],
    )
    if row["notify"]:
        from backend.behavior.gate_alerts import enqueue_alert

        detail = row["detail"] or row["url"] or row["event"]
        enqueue_alert("extension_tab_redirect", detail=detail)
    return _LOG_PATH
