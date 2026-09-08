"""Human-readable gate / morning hints for desktop UI."""

from __future__ import annotations

from typing import Any


def gate_lock_hint(gate: dict[str, Any] | None) -> str:
    """Short line for Calendar empty state / Today."""
    g = gate or {}
    morning = g.get("morning") if isinstance(g.get("morning"), dict) else {}
    if g.get("unlocked") or not g.get("enabled"):
        return "Gate is open — follow your plan or browse per schedule."
    if not g.get("locked"):
        return "Gate monitoring — complete morning steps if browser feels restricted."

    hint = str(morning.get("hint") or "").strip()
    if hint:
        return hint

    try:
        from backend.behavior.tracker_rules import next_step_label

        nxt = str(morning.get("next") or "open")
        pw = morning.get("plan_window") if isinstance(morning.get("plan_window"), dict) else None
        label = next_step_label(nxt, plan_window=pw)
    except Exception:  # noqa: BLE001
        label = str(morning.get("next") or "morning flow")

    parts = [f"Gate locked — next: {label}"]
    if not morning.get("bible_done"):
        parts.append("read today's Bible chapter")
    if not morning.get("plan_confirmed"):
        parts.append("confirm today's plan in Plan tab")
    return " · ".join(parts)
