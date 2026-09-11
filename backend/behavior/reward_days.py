"""Earned free-day credits for the desktop productivity gate.

Four qualifying days (daily productive goal plus Bible chapter) earn one
stackable credit. A credit unlocks FREE mode until midnight via calt_enforcer.
Qualification *decision* stays in distraction_gate until P5c; this module is a
thin gateway caller for status / claim / mark / grant.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.bible import store as bible_store

logger = logging.getLogger(__name__)

CONFIRM_PHRASE = "REWARD"
QUALIFYING_DAYS_PER_REWARD = 4  # display / docs; enforcer owns the maths


def _map_status(reply: dict[str, Any], *, active_today: bool) -> dict[str, Any]:
    qualified = int(reply.get("qualified_days") or 0)
    earned = int(reply.get("reward_earned") or (qualified // QUALIFYING_DAYS_PER_REWARD))
    granted = int(reply.get("reward_granted") or 0)
    spent = int(reply.get("reward_spent") or 0)
    available = int(reply.get("reward_available") or max(0, earned + granted - spent))
    to_next = int(reply.get("days_to_next_reward") or (QUALIFYING_DAYS_PER_REWARD - (qualified % 4)))
    return {
        "qualifying_days": qualified,
        "qualifying_days_per_reward": QUALIFYING_DAYS_PER_REWARD,
        "days_to_next_reward": to_next,
        "earned": earned,
        "granted": granted,
        "spent": spent,
        "available": available,
        "active_today": active_today,
        "confirm_phrase": CONFIRM_PHRASE,
    }


def status(user_id: int) -> dict[str, Any]:
    from backend.behavior.enforcer_gateway import GatewayUnavailable, gateway_call

    day = bible_store.load_day(user_id)
    active = bool(day.get("reward_day"))
    try:
        reply = gateway_call("reward.status")
    except GatewayUnavailable:
        return {
            "qualifying_days": 0,
            "qualifying_days_per_reward": QUALIFYING_DAYS_PER_REWARD,
            "days_to_next_reward": QUALIFYING_DAYS_PER_REWARD,
            "earned": 0,
            "granted": 0,
            "spent": 0,
            "available": 0,
            "active_today": active,
            "confirm_phrase": CONFIRM_PHRASE,
            "gateway_unavailable": True,
        }
    return _map_status(reply, active_today=active)


def grant_credits(user_id: int, count: int = 3) -> dict[str, Any]:
    """Bank bonus reward-day credits (does not invent qualifying history)."""
    from backend.behavior.enforcer_gateway import GatewayUnavailable, gateway_call

    n = int(count)
    if n <= 0:
        raise ValueError("count must be positive")
    try:
        reply = gateway_call("reward.grant_credits", {"count": n})
    except GatewayUnavailable as exc:
        raise ValueError("Enforcer is not running — start CALT Desktop Enforcer") from exc
    if not reply.get("ok"):
        raise ValueError(str(reply.get("error") or "gateway_refused"))
    return status(user_id)


def record_qualifying_day(user_id: int, *, qualified: bool) -> dict[str, Any]:
    """Idempotently record today's completed day; never count reward days.

    Decision stays in distraction_gate; enforcer owns the credit ledger (P5a)
    and earn-minute events (chapter_done / daily_goal).
    """
    from backend.behavior.enforcer_gateway import GatewayUnavailable, gateway_call

    if not qualified or bible_store.load_day(user_id).get("reward_day"):
        return status(user_id)
    try:
        gateway_call("reward.mark_qualified", {})
        gateway_call("day.mark_event", {"event": "chapter_done"})
        # daily_goal earn minutes — best-effort; already-recorded is fine
        gateway_call("day.mark_event", {"event": "daily_goal"})
    except GatewayUnavailable as exc:
        logger.warning("record_qualifying_day gateway unavailable: %s", exc)
    return status(user_id)


def claim_reward_day(user_id: int, *, confirm: str, already_unlocked: bool) -> dict[str, Any]:
    from backend.behavior.enforcer_gateway import GatewayUnavailable, gateway_call

    day = bible_store.load_day(user_id)
    if day.get("reward_day"):
        return {**status(user_id), "ok": True, "message": "Reward day is already active until midnight"}

    # Spec §1 sharp edge 8: refuse organic unlock days at the Python edge until
    # P5c teaches the enforcer day_unlocked. Enforcer's already_unlocked means
    # reward_day_active only.
    if already_unlocked:
        raise ValueError("Today is already unlocked; save the reward day for another day")

    try:
        reply = gateway_call("reward.claim", {"confirm": confirm})
    except GatewayUnavailable as exc:
        raise ValueError("Enforcer is not running — start CALT Desktop Enforcer") from exc

    if not reply.get("ok"):
        err = str(reply.get("error") or "gateway_refused")
        if err == "confirm_required":
            raise ValueError(f"Type {CONFIRM_PHRASE} to use an earned reward day")
        if err == "no_reward_available":
            cur = status(user_id)
            raise ValueError(
                f"Complete {cur['days_to_next_reward']} more qualifying day(s) to earn a reward day"
            )
        if err == "already_unlocked":
            raise ValueError("Reward day is already active until midnight")
        raise ValueError(err)

    day["reward_day"] = True
    bible_store.save_day(user_id, day)
    return {**status(user_id), "ok": True, "message": "Reward day active — free mode until midnight"}
