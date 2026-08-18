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
