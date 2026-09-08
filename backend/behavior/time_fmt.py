"""Human duration labels: hours + minutes (storage still uses minutes)."""

from __future__ import annotations


def format_hours_mins(total_minutes: float | int | None) -> str:
    if total_minutes is None:
        return "—"
    try:
        n = max(0, int(round(float(total_minutes))))
    except (TypeError, ValueError):
        return "—"
    hours, mins = divmod(n, 60)
    h_part = "1 hour" if hours == 1 else f"{hours} hours"
    m_part = "1 min" if mins == 1 else f"{mins} mins"
    if hours == 0:
        return f"{h_part} {m_part}"
    if mins == 0:
        return h_part
    return f"{h_part} {m_part}"


def format_hours_mins_from_hours(hours: float | int | None) -> str:
    if hours is None:
        return "—"
    try:
        return format_hours_mins(float(hours) * 60.0)
    except (TypeError, ValueError):
        return "—"


def optional_minutes_label(total_minutes: float | int | None) -> str | None:
    if total_minutes is None:
        return None
    return format_hours_mins(total_minutes)


def optional_hours_label(hours: float | int | None) -> str | None:
    if hours is None:
        return None
    return format_hours_mins_from_hours(hours)


def format_duration_spoken(total_minutes: float | int | None) -> str:
    """TTS-friendly label — omits a leading ``0 hours`` when under one hour."""
    label = format_hours_mins(total_minutes)
    if label.startswith("0 hours "):
        return label[len("0 hours ") :]
    return label


_MINUTE_KEYS = (
    "focus_min",
    "distracted_min",
    "productive_min",
    "remaining_min",
    "goal_min",
    "daily_goal_min",
    "productive_minutes",
    "remaining_minutes",
    "daily_goal_minutes",
)


def enrich_duration_fmt(fmt: dict[str, object]) -> dict[str, object]:
    """Add ``*_hm`` spoken labels for minute fields present in ``fmt``."""
    out = dict(fmt)
    for key in _MINUTE_KEYS:
        if key not in fmt:
            continue
        hm_key = key.replace("_minutes", "_hm").replace("_min", "_hm")
        if hm_key.endswith("_hm") and hm_key not in out:
            out[hm_key] = format_duration_spoken(fmt[key])
    return out
