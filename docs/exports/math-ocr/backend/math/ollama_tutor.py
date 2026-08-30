"""Optional LLM integration for math tutor hints (gateway text path + direct Ollama vision)."""

from __future__ import annotations

import json
import os
import re

import httpx
from pydantic import BaseModel, Field

from backend.core.ollama_client import llm_reachable, ollama_generate


class SocraticHint(BaseModel):
    hint: str = Field(..., max_length=500)
    question: str = Field(..., max_length=300)
    detected_concept: str = Field(default="", max_length=120)


_ANSWER_RE = re.compile(
    r"(x\s*=\s*[-+]?\d|the answer is|solution:\s*[-+]?\d)",
    re.I,
)

MATH_TUTOR_SYSTEM = """You are a Socratic math tutor. Never give the final answer.
Give a short hint (2 sentences max) and one follow-up question.
Reply as JSON only: {"hint":"...","question":"...","detected_concept":"..."}"""


def ollama_vision_url() -> str | None:
    """Direct Ollama base URL for the vision branch (gateway has no multimodal support)."""
    from backend.config import get_settings

    if not get_settings().ollama_enabled:
        return None
    url = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434").strip().rstrip("/")
    return url or None


def ollama_available() -> str | None:
    """Backward-compatible alias used by OCR status checks."""
    return ollama_vision_url()


def _parse_hint_response(raw: str, topic: str) -> dict | None:
    if not raw:
        return None
    try:
        parsed = json.loads(raw) if raw.strip().startswith("{") else None
        if parsed and "hint" in parsed:
            try:
                hint_obj = SocraticHint.model_validate(parsed)
            except Exception:
                hint_obj = None
            if hint_obj and not _ANSWER_RE.search(f"{hint_obj.hint} {hint_obj.question}"):
                return {
                    "hint": hint_obj.hint,
                    "question": hint_obj.question,
                    "detected_concept": hint_obj.detected_concept or topic,
                }
        return {
            "hint": raw[:500],
            "question": "What is your next step on the board?",
            "detected_concept": topic,
        }
    except Exception:
        return None


def _vision_hint_via_ollama(
    *,
    base: str,
    user_text: str,
    canvas_image: str,
    topic: str,
) -> dict | None:
    vision = os.getenv("OLLAMA_VISION_MODEL", "").strip()
    if not vision:
        return None
    payload = {
        "model": vision,
        "messages": [
            {
                "role": "user",
                "content": user_text,
                "images": [canvas_image.split(",", 1)[-1] if "," in canvas_image else canvas_image],
            }
        ],
        "stream": False,
        "keep_alive": -1,
    }
    try:
        with httpx.Client(timeout=45.0) as client:
            res = client.post(f"{base}/api/chat", json=payload)
            res.raise_for_status()
            data = res.json()
        raw = data.get("response") or data.get("message", {}).get("content", "")
        return _parse_hint_response(raw, topic)
    except Exception:
        return None


def generate_tutor_hint(
    *,
    prompt: str,
    topic: str,
    gamma: float,
    attention: float,
    canvas_image: str,
    llm_tier: str | None = None,
) -> dict | None:
    stress_note = ""
    if gamma > 55 or attention < 45:
        stress_note = "The student's cognitive load appears elevated. Be gentle and break steps down. "

    user_text = (
        f"{stress_note}Topic: {topic}\nProblem: {prompt[:500]}\n"
        "Give a short Socratic hint (2 sentences) and one follow-up question. "
        'Reply as JSON: {"hint":"...","question":"...","detected_concept":"..."}'
    )

    # Hybrid: vision stays on direct Ollama when canvas + vision model are set.
    if canvas_image and len(canvas_image) > 100:
        base = ollama_vision_url()
        vision = os.getenv("OLLAMA_VISION_MODEL", "").strip()
        if base and vision:
            return _vision_hint_via_ollama(
                base=base,
                user_text=user_text,
                canvas_image=canvas_image,
                topic=topic,
            )

    if not llm_reachable():
        return None

    try:
        raw = ollama_generate(
            user_text,
            system_prompt=MATH_TUTOR_SYSTEM,
            task="math_hint",
            tier=llm_tier,
            timeout=45.0,
        )
        return _parse_hint_response(raw or "", topic)
    except Exception:
        return None
