"""Recurring browser gate schedules (Freedom-style windows)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.paths import ROOT

_SCHEDULE_PATH = ROOT / "data" / "behavior" / "gate_schedules.json"

DEFAULT_SCHEDULES: dict[str, Any] = {
    "enabled": False,
    "windows": [
        {
            "id": "weekday-focus",
            "label": "Weekday focus",
            "days": [0, 1, 2, 3, 4],
            "start": "09:00",
            "end": "18:00",
            "mode": "study",
        },
        {
            "id": "evening-free",
            "label": "Evening free",
            "days": [0, 1, 2, 3, 4, 5, 6],
            "start": "22:00",
            "end": "06:00",
            "mode": "free",
        },
    ],
}


def _read() -> dict[str, Any]:
    try:
        if _SCHEDULE_PATH.is_file():
            raw = json.loads(_SCHEDULE_PATH.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                return raw
    except Exception:
        pass
    return dict(DEFAULT_SCHEDULES)


def _write(data: dict[str, Any]) -> dict[str, Any]:
    _SCHEDULE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _SCHEDULE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def load_gate_schedules() -> dict[str, Any]:
    data = _read()
    if "windows" not in data:
        data["windows"] = list(DEFAULT_SCHEDULES["windows"])
    if "enabled" not in data:
        data["enabled"] = False
    return data


def save_gate_schedules(payload: dict[str, Any]) -> dict[str, Any]:
    windows = payload.get("windows")
    if not isinstance(windows, list):
        windows = DEFAULT_SCHEDULES["windows"]
    cleaned: list[dict[str, Any]] = []
    for i, w in enumerate(windows):
        if not isinstance(w, dict):
            continue
        mode = str(w.get("mode") or "study").strip().lower()
        if mode not in ("study", "free", "planning", "bible"):
            mode = "study"
        days_raw = w.get("days") or []
        days = [int(d) for d in days_raw if isinstance(d, (int, float)) and 0 <= int(d) <= 6]
        cleaned.append({
            "id": str(w.get("id") or f"win-{i}"),
            "label": str(w.get("label") or f"Window {i + 1}")[:64],
            "days": days or [0, 1, 2, 3, 4],
            "start": str(w.get("start") or "09:00")[:5],
            "end": str(w.get("end") or "17:00")[:5],
            "mode": mode,
        })
    return _write({
        "enabled": bool(payload.get("enabled")),
        "windows": cleaned or list(DEFAULT_SCHEDULES["windows"]),
    })


def _parse_hm(hm: str) -> int:
    parts = (hm or "00:00").split(":")
    try:
        h = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 else 0
    except (TypeError, ValueError):
        return 0
    return max(0, min(24 * 60, h * 60 + m))


def _in_window(now: datetime, start_min: int, end_min: int) -> bool:
    cur = now.hour * 60 + now.minute
    if start_min <= end_min:
        return start_min <= cur < end_min
    return cur >= start_min or cur < end_min


def scheduled_mode(now: datetime | None = None) -> str | None:
    """Return forced mode if a schedule window matches, else None."""
    data = load_gate_schedules()
    if not data.get("enabled"):
        return None
    dt = now if now is not None else datetime.now().astimezone()
    if dt.tzinfo is None:
        dt = dt.astimezone()
    weekday = dt.weekday()
    for win in data.get("windows") or []:
        days = win.get("days") or []
        if days and weekday not in days:
            continue
        start = _parse_hm(str(win.get("start") or "00:00"))
        end = _parse_hm(str(win.get("end") or "23:59"))
        if _in_window(dt, start, end):
            mode = str(win.get("mode") or "study").strip().lower()
            if mode in ("study", "free", "planning", "bible"):
                return mode
    return None
