"""RescueTime-style Productivity Pulse — time-weighted level score 0–100."""

from __future__ import annotations

from typing import Any

from backend.behavior.category_scores import PRODUCTIVE_THRESHOLD


def level_weight(score: int | float | None) -> int:
    """Map raw productivity score to five-level pulse weight."""
    s = int(score or 0)
    if s >= 80:
        return 100
    if s >= 60:
        return 75
    if s >= 40:
        return 50
    if s >= 20:
        return 25
    return 0


def pulse_label(pulse: int) -> str:
    if pulse >= 80:
        return "Very productive"
    if pulse >= 60:
        return "Productive"
    if pulse >= 40:
        return "Neutral"
    if pulse >= 20:
        return "Distracting"
    return "Very distracting"


def _accumulate(
    seconds: int,
    score: int | float | None,
    *,
    total: int,
    weighted: int,
    productive: int,
    distracting: int,
) -> tuple[int, int, int, int]:
    if seconds <= 0:
        return total, weighted, productive, distracting
    sc = int(score or 0)
    total += seconds
    weighted += seconds * level_weight(sc)
    if sc >= PRODUCTIVE_THRESHOLD:
        productive += seconds
    elif sc < 40:
        distracting += seconds
    return total, weighted, productive, distracting


def compute_pulse_from_sessions(sessions: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute pulse from desktop-stats session list (apps + nested sites)."""
    total = weighted = productive = distracting = 0

    for session in sessions:
        if session.get("kind") == "browser" and session.get("sites"):
            for site in session["sites"]:
                total, weighted, productive, distracting = _accumulate(
                    int(site.get("seconds") or 0),
                    site.get("productivity_score"),
                    total=total,
                    weighted=weighted,
                    productive=productive,
                    distracting=distracting,
                )
        else:
            total, weighted, productive, distracting = _accumulate(
                int(session.get("seconds") or 0),
                session.get("productivity_score"),
                total=total,
                weighted=weighted,
                productive=productive,
                distracting=distracting,
            )

    pulse = round(weighted / total) if total else 0
    return {
        "pulse": pulse,
        "pulse_label": pulse_label(pulse),
        "productive_seconds": productive,
        "distracting_seconds": distracting,
        "total_seconds": total,
    }


def attach_pulse(payload: dict[str, Any]) -> dict[str, Any]:
    """Merge pulse fields into a desktop-stats-like dict."""
    sessions = payload.get("sessions") or []
    pulse = compute_pulse_from_sessions(sessions)
    payload.update(pulse)
    return payload
