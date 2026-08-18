"""Preprocess watch clock stamps; postprocess ingest day + timezone.

Zepp OS 6 companion path: Device App stamps local_date / tz_offset_min /
captured_at on the watch, BLE carries that to the phone Side Service, HTTP
ingest must not replace it with the phone or PC 'today'.
"""

from __future__ import annotations

from datetime import date, timedelta, timezone
import json
from typing import Any
from zoneinfo import ZoneInfo

from backend.planner.service import local_tz


def tz_from_offset_min(offset_min: int | float | None) -> timezone | ZoneInfo:
    """Fixed offset east of UTC in minutes (JS Date.getTimezoneOffset() inverted)."""
    if offset_min is None:
        return local_tz()
    try:
        minutes = int(offset_min)
    except (TypeError, ValueError):
        return local_tz()
    minutes = max(-14 * 60, min(14 * 60, minutes))
    return timezone(timedelta(minutes=minutes))


def _parse_day(raw: Any) -> date | None:
    if raw is None:
        return None
    text = str(raw).strip()[:10]
    if len(text) < 10:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def resolve_ingest_day(body: dict[str, Any] | None, *, host_today: date) -> date:
    """Prefer the watch calendar day. Host today is only a fallback/guard."""
    body = body or {}
    meta = body.get("meta") if isinstance(body.get("meta"), dict) else {}
    watch_day = _parse_day(body.get("local_date")) or _parse_day(meta.get("watch_local_date"))
    if watch_day is None:
        return host_today

    queued = bool(meta.get("queued_sleep_snapshot")) or bool(meta.get("chunk"))
    source = str(body.get("source") or "").strip().lower()
    trusted = source in ("mini_program", "zepp", "amazfit")
    allowed = 7 if queued and trusted else 1
    if abs((watch_day - host_today).days) > allowed:
        return host_today
    return watch_day


def clock_fields_from_payload(payload: dict[str, Any] | str | None) -> dict[str, Any]:
    """First-class watch clock stamps for API responses (not buried in payload)."""
    raw: Any = payload
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            raw = None
    if not isinstance(raw, dict):
        return {"tz_offset_min": None, "watch_local_date": None, "captured_at": None}
    meta = raw.get("meta") if isinstance(raw.get("meta"), dict) else {}
    offset = meta.get("tz_offset_min")
    if offset is None:
        offset = raw.get("tz_offset_min")
    try:
        tz_out = int(offset) if offset is not None else None
    except (TypeError, ValueError):
        tz_out = None
    watch_day = meta.get("watch_local_date") or raw.get("local_date")
    if watch_day is not None:
        text = str(watch_day).strip()[:10]
        watch_day = text if len(text) == 10 else None
    captured = raw.get("captured_at")
    if captured is not None:
        captured = str(captured).strip() or None
    return {
        "tz_offset_min": tz_out,
        "watch_local_date": watch_day,
        "captured_at": captured,
    }


def tz_from_payload(payload: dict[str, Any] | str | None) -> timezone | ZoneInfo:
    """Read watch tz_offset_min from a stored dump JSON."""
    raw: Any = payload
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return local_tz()
    if not isinstance(raw, dict):
        return local_tz()
    meta = raw.get("meta") if isinstance(raw.get("meta"), dict) else {}
    offset = meta.get("tz_offset_min")
    if offset is None:
        offset = raw.get("tz_offset_min")
    return tz_from_offset_min(offset)
