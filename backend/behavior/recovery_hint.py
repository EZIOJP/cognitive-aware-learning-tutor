"""Watch sleep → suggested daily focus capacity (Whoop / RescueTime borrow)."""

from __future__ import annotations

from typing import Any


def compute_recovery_hint(
    *,
    sleep_score: int | float | None = None,
    sleep_hours: float | None = None,
    base_focus_hours: float = 4.0,
) -> dict[str, Any]:
    """Return factor + suggested focus hours from wearables sleep signals."""
    base = max(0.5, min(16.0, float(base_focus_hours or 4.0)))
    score: int | None = None
    if sleep_score is not None:
        try:
            score = int(sleep_score)
            if score <= 0:
                score = None
        except (TypeError, ValueError):
            score = None

    hours: float | None = None
    if sleep_hours is not None:
        try:
            hours = float(sleep_hours)
            if hours <= 0:
                hours = None
        except (TypeError, ValueError):
            hours = None

    if score is not None:
        if score >= 85:
            factor, label = 1.0, "Full capacity"
        elif score >= 70:
            factor, label = 0.9, "Good recovery"
        elif score >= 55:
            factor, label = 0.75, "Moderate — trim deep work"
        else:
            factor, label = 0.6, "Low recovery — lighter day"
        return {
            "sleep_score": score,
            "sleep_hours": hours,
            "factor": factor,
            "label": label,
            "suggested_focus_hours": round(base * factor, 1),
            "base_focus_hours": base,
        }

    if hours is not None and hours < 6.0:
        factor = 0.7
        return {
            "sleep_score": None,
            "sleep_hours": hours,
            "factor": factor,
            "label": "Short sleep",
            "suggested_focus_hours": round(base * factor, 1),
            "base_focus_hours": base,
        }

    return {
        "sleep_score": score,
        "sleep_hours": hours,
        "factor": 1.0,
        "label": "No watch data",
        "suggested_focus_hours": round(base, 1),
        "base_focus_hours": base,
    }
