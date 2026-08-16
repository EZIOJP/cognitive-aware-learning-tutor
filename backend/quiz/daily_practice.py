"""Soft daily-practice nudge after morning plan (no gate lock)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session


def build_daily_practice_nudge(db: Session, *, user_id: int) -> dict[str, Any]:
    """CTA payload for Review Hub / vocab — never blocks Soft-land."""
    try:
        from backend.quiz.next_step import compute_next_step

        step = compute_next_step(db, user_id=user_id)
    except Exception:
        step = {
            "action": "review_due",
            "label": "Daily practice",
            "to": "/review?tab=due",
            "reason": "Spaced practice after planning.",
            "due_count": 0,
        }

    due = int(step.get("due_count") or 0)
    action = str(step.get("action") or "review_due")
    to = str(step.get("to") or "/review?tab=due")
    label = str(step.get("label") or "Daily practice")
    if due > 0 and action == "review_due":
        label = f"Daily practice — {due} due"
    elif action == "start_vocab":
        label = "Daily practice — vocab read → quiz"
    elif due == 0 and action not in ("sign_in",):
        label = label if label else "Daily practice"
        if "practice" not in label.lower() and "review" not in label.lower():
            label = f"Daily practice — {label}"

    return {
        "show": True,
        "due_count": due,
        "action": action,
        "label": label,
        "to": to,
        "reason": str(step.get("reason") or ""),
    }
