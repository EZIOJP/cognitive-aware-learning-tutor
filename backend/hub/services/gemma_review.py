"""Daily AI review via NVIDIA NIM (Gemma) when NIM_API_KEY is set."""

from __future__ import annotations

import json

from backend.integrations.nim_client import nim_chat_json, nim_available
from backend.math.training_log import training_stats_for_hub


async def generate_daily_review(hub_payload: dict, *, user_id: int) -> dict:
    if not nim_available():
        raise RuntimeError("NIM_API_KEY not configured")

    ocr_stats = training_stats_for_hub(user_id)
    payload = {**hub_payload, **ocr_stats}

    prompt = f"""You are JP's study companion. Speak like a direct, warm friend.
Never say 'optimize' or 'productivity'. Max 3 next steps.

Today's data:
{json.dumps(payload, indent=2)}

Return JSON only:
{{"comments": "...", "next_steps": ["..."], "goals": ["..."]}}"""

    parsed = await nim_chat_json([{"role": "user", "content": prompt}])
    comments = str(parsed.get("comments", "")).strip()
    steps = parsed.get("next_steps") or []
    goals = parsed.get("goals") or []
    if not comments:
        raise ValueError("Empty NIM review")

    return {
        "comments": comments[:800],
        "next_steps": [str(s)[:200] for s in steps[:5]],
        "goals": [str(g)[:120] for g in goals[:5]],
        "overall_performance": hub_payload.get("overall_performance", "good"),
        "source": "gemma",
    }
