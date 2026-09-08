"""Natural-language day commands for voice agent."""

from __future__ import annotations

import re
from typing import Any


def try_day_command(user_id: int, text: str) -> str | None:
    """Parse plain phrases; None if not a day command."""
    if not user_id:
        return "Link your account first."
    t = (text or "").strip().lower()
    if not t:
        return None

    if re.search(r"\b(apply|build|plan)\s+(my\s+)?day\b", t) or t in ("apply my day", "build my day"):
        from backend.behavior.calt_desktop.day_coach import apply_my_day

        res = apply_my_day(user_id)
        if not res.get("ok"):
            return str(res.get("error") or "Apply failed")
        return (
            f"Applied your day: {res.get('routines_created', 0)} routines, "
            f"{res.get('study_created', 0)} study blocks."
        )

    if re.search(r"\brevert\b.*\b(apply|plan|day)\b", t) or t == "undo apply":
        from backend.behavior.calt_desktop.apply_snapshot import revert_last_apply

        res = revert_last_apply(user_id)
        if not res.get("ok"):
            return str(res.get("error") or "Nothing to revert")
        return f"Reverted: removed {res.get('removed', 0)}, restored {res.get('restored', 0)}."

    m = re.search(r"\bgate\s+free\b.*?(\d+)\s*(min|minute)", t)
    if m or "gate free" in t:
        mins = int(m.group(1)) if m else 30
        from backend.behavior.browser_gate_policy import set_free_override

        set_free_override(minutes=mins)
        return f"Gate free for {mins} minutes."

    if re.search(r"\b(finished|done with)\s+(breakfast|lunch|dinner|bath|bible)\b", t):
        from backend.behavior.calt_desktop.block_gate import active_block_now
        from backend.behavior.calt_desktop.devotion_sync import mark_devotion_for_block

        block = active_block_now(user_id)
        if block and "bible" in t:
            return mark_devotion_for_block(user_id, block)
        return "Noted — keep going with your plan."

    m = re.search(r"\bmove\s+(.+?)\s+to\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", t)
    if m:
        return (
            f"To move {m.group(1)} to {m.group(2)}, open Plan → Today's blocks and edit the time."
        )

    if "what's next" in t or "whats next" in t or "next block" in t:
        from backend.behavior.calt_desktop.block_gate import active_block_now, next_block

        cur = active_block_now(user_id)
        if cur:
            return f"Now: {cur.get('title')} until {cur.get('end_local', '?')}."
        nxt = next_block(user_id)
        if nxt:
            return f"Next: {nxt.get('title')} at {nxt.get('start_local', '?')}."
        return "No more blocks on today's plan."

    return None
