"""Optional Ollama integration for math tutor hints."""

from __future__ import annotations

import json
import os

import httpx


def ollama_available() -> str | None:
    from backend.config import get_settings

    if not get_settings().ollama_enabled:
        return None
    url = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434").strip().rstrip("/")
    return url or None


def generate_tutor_hint(
    *,
    prompt: str,
    topic: str,
    gamma: float,
    attention: float,
    canvas_image: str,
) -> dict | None:
    base = ollama_available()
    if not base:
        return None

    model = os.getenv("OLLAMA_MODEL", "llama3.2").strip()
    stress_note = ""
    if gamma > 55 or attention < 45:
        stress_note = "The student's cognitive load appears elevated. Be gentle and break steps down. "

    user_text = (
        f"{stress_note}Topic: {topic}\nProblem: {prompt[:500]}\n"
        "Give a short Socratic hint (2 sentences) and one follow-up question. "
        'Reply as JSON: {"hint":"...","question":"...","detected_concept":"..."}'
    )

    payload: dict = {
        "model": model,
        "prompt": user_text,
        "stream": False,
        "format": "json",
    }
    if canvas_image and len(canvas_image) > 100:
        vision = os.getenv("OLLAMA_VISION_MODEL", "").strip()
        if vision:
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
            }
            path = f"{base}/api/chat"
        else:
            path = f"{base}/api/generate"
    else:
        path = f"{base}/api/generate"

    try:
        with httpx.Client(timeout=45.0) as client:
            res = client.post(path, json=payload)
            res.raise_for_status()
            data = res.json()
        raw = data.get("response") or data.get("message", {}).get("content", "")
        if not raw:
            return None
        parsed = json.loads(raw) if raw.strip().startswith("{") else None
        if parsed and "hint" in parsed:
            return {
                "hint": str(parsed.get("hint", ""))[:500],
                "question": str(parsed.get("question", ""))[:300],
                "detected_concept": str(parsed.get("detected_concept", topic))[:120],
            }
        return {
            "hint": raw[:500],
            "question": "What is your next step on the board?",
            "detected_concept": topic,
        }
    except Exception:
        return None
