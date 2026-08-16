"""AI nutrition estimate (text) + plate photo suggestions (vision) via Gemini."""

from __future__ import annotations

import base64
import json
import logging
import os
import re
from typing import Any

import httpx

from backend.core.ollama_client import GEMINI_API_BASE, LlmOptions, _gemini_auth_headers, _parse_gemini_output

log = logging.getLogger("nutrition.ai")

_ESTIMATE_PROMPT = """You are a nutrition estimator for Indian and global home cooking.
Given a food name and portion weight in grams, estimate macros.

Respond ONLY with valid JSON (no markdown):
{
  "food_name": "<normalized lowercase name>",
  "per_100g": {
    "kcal": <number>,
    "protein_g": <number>,
    "carbs_g": <number>,
    "fat_g": <number>,
    "fiber_g": <number>
  },
  "confidence": <0.0 to 1.0>,
  "notes": "<one short sentence>"
}
"""

_PHOTO_PROMPT = """You are a nutrition assistant looking at a plate or food photo.
Suggest discrete food items the user can confirm (do not invent macros).

Respond ONLY with valid JSON (no markdown):
{
  "items": [
    {
      "suggested_name": "<common food name>",
      "estimated_weight_g": <optional number or null>,
      "confidence": <0.0 to 1.0>
    }
  ],
  "description": "<one sentence>"
}
List 1-6 items. Prefer common Indian dish names when appropriate.
"""


def _gemini_api_key() -> str:
    from backend.config import get_settings

    s = get_settings()
    for candidate in (
        getattr(s, "llm_cloud_api_key", "") or "",
        os.environ.get("LLM_CLOUD_API_KEY", "") or "",
        os.environ.get("GEMINI_API_KEY", "") or "",
        getattr(s, "llm_api_key", "") or "",
        os.environ.get("LLM_API_KEY", "") or "",
    ):
        key = (candidate or "").strip()
        if key and key.lower() not in {"changeme", "your-key-here", "your-key-from-aistudio.google.com"}:
            return key
    return ""


def _strip_json(raw: str) -> str:
    text = (raw or "").strip()
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1] if len(parts) > 1 else text
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()
    m = re.search(r"\{.*\}", text, re.DOTALL)
    return m.group(0) if m else text


def _gemini_generate_parts(
    parts: list[dict[str, Any]],
    *,
    system_prompt: str | None = None,
    model: str = "gemini-2.0-flash",
    timeout: float = 45.0,
    max_tokens: int = 1024,
) -> str | None:
    api_key = _gemini_api_key()
    if not api_key:
        log.warning("Gemini key missing for nutrition AI")
        return None

    model = model.replace("models/", "")
    payload: dict[str, Any] = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": max_tokens,
        },
    }
    if system_prompt:
        payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}

    url = f"{GEMINI_API_BASE}/models/{model}:generateContent"
    try:
        with httpx.Client(timeout=timeout) as client:
            res = client.post(url, headers=_gemini_auth_headers(api_key), json=payload)
            res.raise_for_status()
            return _parse_gemini_output(res.json())
    except Exception as exc:
        log.warning("Gemini nutrition call failed: %s", exc)
        return None


def _per_g_from_100(per_100: dict[str, Any]) -> dict[str, float]:
    return {
        "kcal": float(per_100.get("kcal") or 0) / 100.0,
        "p": float(per_100.get("protein_g") or 0) / 100.0,
        "c": float(per_100.get("carbs_g") or 0) / 100.0,
        "f": float(per_100.get("fat_g") or 0) / 100.0,
        "fiber": float(per_100.get("fiber_g") or 0) / 100.0,
    }


def estimate_nutrition(food_name: str, weight_g: float) -> dict[str, Any]:
    """Return macros for weight_g plus per_g for optional custom save."""
    from backend.plugins.nutrition_foods import macros_for_weight

    prompt = (
        f"Food: {food_name.strip()}\n"
        f"Portion weight: {float(weight_g):.1f} g\n"
        "Estimate typical cooked / as-eaten values."
    )
    raw = _gemini_generate_parts(
        [{"text": prompt}],
        system_prompt=_ESTIMATE_PROMPT,
    )
    if not raw:
        # Fallback: gateway text path
        try:
            from backend.core.llm_gateway import llm_complete

            result = llm_complete(
                f"{_ESTIMATE_PROMPT}\n\n{prompt}",
                task="generic",
                llm=LlmOptions(max_tokens=512),
            )
            raw = result.text if result and result.text else None
        except Exception as exc:
            log.warning("Gateway nutrition estimate failed: %s", exc)
            raw = None

    if not raw:
        raise RuntimeError("AI nutrition estimate unavailable — configure LLM_CLOUD_API_KEY")

    data = json.loads(_strip_json(raw))
    per_100 = data.get("per_100g") or {}
    per_g = _per_g_from_100(per_100)
    macros = macros_for_weight(per_g, weight_g)
    return {
        **macros,
        "food_name": (data.get("food_name") or food_name).strip().lower(),
        "macros_source": "ai",
        "confidence": float(data.get("confidence") or 0.5),
        "notes": data.get("notes") or "",
        "per_g": per_g,
        "per_100g": {
            "kcal": round(per_g["kcal"] * 100, 1),
            "protein_g": round(per_g["p"] * 100, 1),
            "carbs_g": round(per_g["c"] * 100, 1),
            "fat_g": round(per_g["f"] * 100, 1),
            "fiber_g": round(per_g["fiber"] * 100, 1),
        },
    }


def analyze_photo(image_bytes: bytes, mime: str = "image/jpeg") -> dict[str, Any]:
    """Vision → suggested food names (user still confirms weight)."""
    b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
    media = mime if mime in ("image/jpeg", "image/png", "image/webp") else "image/jpeg"
    raw = _gemini_generate_parts(
        [
            {"inlineData": {"mimeType": media, "data": b64}},
            {"text": "Identify foods on this plate for logging."},
        ],
        system_prompt=_PHOTO_PROMPT,
        max_tokens=1024,
    )
    if not raw:
        raise RuntimeError("Photo analysis unavailable — configure LLM_CLOUD_API_KEY")

    data = json.loads(_strip_json(raw))
    items = []
    for it in data.get("items") or []:
        name = str(it.get("suggested_name") or "").strip()
        if not name:
            continue
        weight = it.get("estimated_weight_g")
        items.append(
            {
                "suggested_name": name,
                "estimated_weight_g": float(weight) if weight is not None else None,
                "confidence": float(it.get("confidence") or 0.5),
            }
        )
    return {
        "items": items,
        "description": data.get("description") or "",
        "source": "gemini_vision",
    }
