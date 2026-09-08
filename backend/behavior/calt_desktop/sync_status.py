"""Read wearables + voice sync timestamps for desktop Watch/Voice tabs."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from backend.paths import ROOT
from backend.planner.service import local_tz

_WEARABLES_SYNC = ROOT / "data" / "wearables_last_sync.json"


def read_wearables_sync() -> dict[str, Any]:
    try:
        if _WEARABLES_SYNC.is_file():
            data = json.loads(_WEARABLES_SYNC.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        pass
    return {}


def format_sync_label(iso_value: str | None, *, empty: str = "never") -> str:
    raw = str(iso_value or "").strip()
    if not raw:
        return empty
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=local_tz())
        local = dt.astimezone(local_tz())
        return local.strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return raw[:19] if len(raw) > 19 else raw


def wearables_sync_summary() -> tuple[str, str]:
    """Return (label, detail) for CALT Sync last activity."""
    state = read_wearables_sync()
    at = (
        state.get("last_ingest_at")
        or state.get("updated_at")
        or state.get("last_plans_at")
        or state.get("last_calendar_at")
    )
    label = format_sync_label(str(at) if at else None)
    parts: list[str] = []
    if state.get("last_event"):
        parts.append(str(state["last_event"]))
    if state.get("last_local_date"):
        parts.append(f"day {state['last_local_date']}")
    if state.get("last_steps") is not None:
        parts.append(f"{state['last_steps']} steps")
    detail = " · ".join(parts) if parts else "No wearables ingest recorded yet"
    return label, detail


def voice_sync_summary() -> tuple[str, str]:
    from backend.behavior.voice_notes import read_sync_state, list_notes

    state = read_sync_state()
    at = state.get("last_upload_at")
    label = format_sync_label(str(at) if at else None)
    rows = list_notes()
    last_name = str(state.get("last_name") or "").strip()
    if last_name:
        last_size = int(state.get("last_size") or 0)
        size_txt = (
            f"{last_size} B"
            if last_size < 1024
            else f"{max(1, round(last_size / 1024))} KB"
        )
        on_disk = any(str(r.get("name") or "") == last_name for r in rows)
        if on_disk:
            detail = f"Last clip {last_name} ({size_txt})"
        else:
            detail = (
                f"Last clip {last_name} ({size_txt}) — missing from disk; "
                "tap clip on watch to resend"
            )
    elif rows:
        detail = f"{len(rows)} clip(s) on disk"
    else:
        detail = "No voice upload finished yet"
    return label, detail
