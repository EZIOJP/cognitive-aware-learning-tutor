"""Daily AI review via LLM gateway (heavy tier; NIM in chain when configured)."""

from __future__ import annotations

import json

from backend.core.ollama_client import ollama_generate
from backend.hub.services.local_coach import _parse_json_blob
from backend.math.training_log import training_stats_for_hub

REVIEW_SYSTEM = """You are JP's study companion. Speak like a direct, warm friend.
Never say 'optimize' or 'productivity'. Max 3 next steps.
Return JSON only with keys: comments (string), next_steps (array of strings), goals (array of strings)."""


def generate_daily_review(
    hub_payload: dict,
    *,
    user_id: int,
    llm_tier: str | None = None,
) -> dict:
    ocr_stats = training_stats_for_hub(user_id)
    payload = {**hub_payload, **ocr_stats}

    prompt = f"""Today's data:
{json.dumps(payload, indent=2)}

Write the daily review JSON now."""

    raw = ollama_generate(
        prompt,
        system_prompt=REVIEW_SYSTEM,
        task="daily_review",
        tier=llm_tier,
        timeout=90.0,
    )
    if not raw:
        raise ValueError("Empty daily review response")

    parsed = _parse_json_blob(raw)
    comments = str(parsed.get("comments", "")).strip()
    steps = parsed.get("next_steps") or []
    goals = parsed.get("goals") or []
    if not comments:
        raise ValueError("Empty review comments")

    return {
        "comments": comments[:800],
        "next_steps": [str(s)[:200] for s in steps[:5]],
        "goals": [str(g)[:120] for g in goals[:5]],
        "overall_performance": hub_payload.get("overall_performance", "good"),
        "source": "gemma",
    }
