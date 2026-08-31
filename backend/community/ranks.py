"""Public rank card — pulse + display name only."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from backend.community.network import peer_url_allowed
from backend.community.store import load_settings
from backend.models import User


def local_card(db: Session, user: User) -> dict[str, Any]:
    from backend.behavior.day_productivity import build_productivity_snapshot

    snap = build_productivity_snapshot(db, user.id, day=date.today())
    name = (user.display_name or "").strip() or user.username
    return {
        "display_name": name,
        "pulse": int(snap.get("pulse") or 0),
        "pulse_label": snap.get("pulse_label") or "No data",
        "day": date.today().isoformat(),
        "you": True,
        "reachable": True,
    }


def fetch_peer_card(base_url: str, *, timeout: float = 2.5) -> dict[str, Any] | None:
    if not peer_url_allowed(base_url):
        return None
    url = f"{base_url.rstrip('/')}/api/community/public-card"
    req = urllib.request.Request(url, headers={"Accept": "application/json"}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if getattr(resp, "status", 200) != 200:
                return None
            body = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError, ValueError):
        return None
    if not isinstance(body, dict):
        return None
    name = str(body.get("display_name") or "").strip()[:80]
    try:
        pulse = int(body.get("pulse") or 0)
    except (TypeError, ValueError):
        pulse = 0
    pulse = max(0, min(100, pulse))
    if not name:
        return None
    return {
        "display_name": name,
        "pulse": pulse,
        "pulse_label": str(body.get("pulse_label") or "")[:80] or None,
        "day": str(body.get("day") or "")[:16] or None,
        "you": False,
        "reachable": True,
        "peer": base_url,
    }


def build_ranks(db: Session, user: User) -> dict[str, Any]:
    settings = load_settings()
    rows: list[dict[str, Any]] = [local_card(db, user)]
    unreachable: list[str] = []
    for peer in settings.get("peers") or []:
        card = fetch_peer_card(str(peer))
        if card:
            rows.append(card)
        else:
            unreachable.append(str(peer))
    rows.sort(key=lambda r: (-int(r.get("pulse") or 0), str(r.get("display_name") or "")))
    for i, row in enumerate(rows, start=1):
        row["rank"] = i
    return {
        "publish_ranks": bool(settings.get("publish_ranks")),
        "rows": rows,
        "unreachable": unreachable,
        "peer_count": len(settings.get("peers") or []),
    }
