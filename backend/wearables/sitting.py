"""Extract sitting / sedentary minutes from Zepp-style wearable payloads."""

from __future__ import annotations

from typing import Any


def _as_int(v: Any) -> int | None:
    if v is None or isinstance(v, bool):
        return None
    try:
        n = int(v)
    except (TypeError, ValueError):
        return None
    if n < 0:
        return None
    return n


def extract_sitting_minutes(body: dict[str, Any] | None) -> int | None:
    """Return sitting/sedentary minutes if the watch payload exposes them.

    Amazfit / Zepp mini-program dumps commonly send ``stand.hours`` only.
    Sitting minutes appear under activity extras on some firmwares; we do
    **not** invent sitting from stand hours.
    """
    if not isinstance(body, dict):
        return None

    # Top-level shortcuts
    for key in ("sitting_min", "sedentary_min", "sit_minutes", "sitting_minutes"):
        n = _as_int(body.get(key))
        if n is not None:
            return n

    sitting = body.get("sitting") or body.get("sedentary")
    if isinstance(sitting, dict):
        for key in ("minutes", "min", "sitting_min", "sedentary_min", "value"):
            n = _as_int(sitting.get(key))
            if n is not None:
                return n
    elif sitting is not None:
        n = _as_int(sitting)
        if n is not None:
            return n

    activity = body.get("activity")
    if isinstance(activity, dict):
        for key in (
            "sitting_min",
            "sedentary_min",
            "sit_minutes",
            "sitting_minutes",
            "inactive_min",
        ):
            n = _as_int(activity.get(key))
            if n is not None:
                return n

    return None


def stand_summary(body: dict[str, Any] | None) -> dict[str, Any]:
    """Compact stand + optional sitting for UI / sync status."""
    body = body if isinstance(body, dict) else {}
    stand = body.get("stand") if isinstance(body.get("stand"), dict) else {}
    hours = _as_int(stand.get("hours"))
    target = _as_int(stand.get("target"))
    sitting = extract_sitting_minutes(body)
    return {
        "stand_hours": hours,
        "stand_target": target,
        "sitting_min": sitting,
        "has_sitting": sitting is not None,
        "label": _label(hours, target, sitting),
    }


def _label(hours: int | None, target: int | None, sitting: int | None) -> str | None:
    parts: list[str] = []
    if hours is not None:
        if target is not None:
            parts.append(f"Stand {hours}/{target}h")
        else:
            parts.append(f"Stand {hours}h")
    if sitting is not None:
        from backend.behavior.time_fmt import format_hours_mins

        parts.append(f"Sitting {format_hours_mins(sitting)}")
    return " · ".join(parts) if parts else None
