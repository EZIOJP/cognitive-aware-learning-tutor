"""Snapshot planner blocks before Apply — enables Revert last apply."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

from backend.paths import ROOT

_SNAPSHOT_PATH = ROOT / "data" / "behavior" / "planner_apply_snapshot.json"


def _read() -> dict[str, Any]:
    if not _SNAPSHOT_PATH.is_file():
        return {}
    try:
        data = json.loads(_SNAPSHOT_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def _write(data: dict[str, Any]) -> None:
    _SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    _SNAPSHOT_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def save_before_apply(
    user_id: int,
    *,
    day: date | None = None,
    label: str = "apply",
) -> int:
    """Store today's block ids + payloads; returns count snapshotted."""
    from backend.behavior.calt_desktop.planner_data import blocks_for_day

    day = day or date.today()
    blocks = blocks_for_day(user_id, day)
    payload = {
        "user_id": user_id,
        "day": day.isoformat(),
        "label": label,
        "saved_at": datetime.now().astimezone().isoformat(),
        "blocks": [
            {
                "id": b.get("id"),
                "title": b.get("title"),
                "category": b.get("category"),
                "start_at": b.get("start_at"),
                "end_at": b.get("end_at"),
                "status": b.get("status"),
            }
            for b in blocks
            if b.get("id")
        ],
    }
    _write(payload)
    return len(payload["blocks"])


def has_snapshot(user_id: int, *, day: date | None = None) -> bool:
    data = _read()
    if int(data.get("user_id") or 0) != user_id:
        return False
    if day and str(data.get("day") or "") != day.isoformat():
        return False
    return bool(data.get("blocks"))


def revert_last_apply(user_id: int) -> dict[str, Any]:
    """Delete blocks created after snapshot; restore snapshotted rows."""
    from backend.behavior.calt_desktop.planner_data import blocks_for_day, create_block, delete_block

    data = _read()
    if int(data.get("user_id") or 0) != user_id:
        return {"ok": False, "error": "no snapshot for this user"}
    day_s = str(data.get("day") or date.today().isoformat())
    y, mo, d = (int(x) for x in day_s.split("-"))
    day = date(y, mo, d)
    snap_ids = {int(b["id"]) for b in data.get("blocks") or [] if b.get("id")}
    current = blocks_for_day(user_id, day)
    current_ids = {int(b["id"]) for b in current if b.get("id")}

    removed = 0
    for bid in current_ids - snap_ids:
        try:
            delete_block(user_id, bid)
            removed += 1
        except Exception:  # noqa: BLE001
            pass

    restored = 0
    for raw in data.get("blocks") or []:
        bid = int(raw.get("id") or 0)
        if bid in current_ids:
            continue
        try:
            start = datetime.fromisoformat(str(raw["start_at"]).replace("Z", "+00:00"))
            end = datetime.fromisoformat(str(raw["end_at"]).replace("Z", "+00:00"))
            create_block(
                user_id,
                day=day,
                title=str(raw.get("title") or "Block"),
                category=str(raw.get("category") or "study"),
                start_hour=start.astimezone().hour,
                start_minute=start.astimezone().minute,
                end_hour=end.astimezone().hour,
                end_minute=end.astimezone().minute,
            )
            restored += 1
        except Exception:  # noqa: BLE001
            pass

    return {
        "ok": True,
        "removed": removed,
        "restored": restored,
        "snapshot_count": len(snap_ids),
        "label": data.get("label"),
    }
