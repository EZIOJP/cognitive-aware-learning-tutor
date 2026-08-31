"""Local JSON for opt-in ranks. Default: publish_ranks False."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from backend.paths import ROOT

SETTINGS_PATH = ROOT / "data" / "behavior" / "community.json"
_lock = threading.Lock()


def default_settings() -> dict[str, Any]:
    return {"publish_ranks": False, "peers": []}


def load_settings() -> dict[str, Any]:
    base = default_settings()
    try:
        raw = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return base
    if not isinstance(raw, dict):
        return base
    base["publish_ranks"] = bool(raw.get("publish_ranks"))
    peers = raw.get("peers") or []
    if isinstance(peers, list):
        cleaned: list[str] = []
        for p in peers:
            if isinstance(p, str) and p.strip():
                cleaned.append(p.strip().rstrip("/"))
            elif isinstance(p, dict) and p.get("url"):
                cleaned.append(str(p["url"]).strip().rstrip("/"))
        base["peers"] = cleaned
    return base


def save_settings(payload: dict[str, Any]) -> dict[str, Any]:
    from backend.community.network import peer_url_allowed, public_base_from_peer

    current = default_settings()
    current["publish_ranks"] = bool(payload.get("publish_ranks"))
    peers_in = payload.get("peers") or []
    peers: list[str] = []
    if isinstance(peers_in, list):
        for item in peers_in:
            url = item.strip() if isinstance(item, str) else str((item or {}).get("url") or "").strip()
            if not url:
                continue
            base = public_base_from_peer(url)
            if base and peer_url_allowed(base) and base not in peers:
                peers.append(base)
    current["peers"] = peers
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        SETTINGS_PATH.write_text(json.dumps(current, indent=2), encoding="utf-8")
    return current
