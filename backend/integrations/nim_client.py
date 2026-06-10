"""NVIDIA NIM cloud client — text + optional vision. Key from env only."""

from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx

_DEFAULT_BASE = "https://integrate.api.nvidia.com/v1"
_JSON_BLOCK = re.compile(r"\{[\s\S]*\}")


def _api_key() -> str:
    return os.getenv("NIM_API_KEY", "").strip()


def _base_url() -> str:
    return os.getenv("NIM_BASE_URL", _DEFAULT_BASE).strip().rstrip("/")


def nim_available() -> bool:
    return bool(_api_key())


def _default_model() -> str:
    return os.getenv("NIM_MODEL", "google/gemma-4-31b-it").strip()


def _vision_model() -> str:
    return os.getenv("NIM_VISION_MODEL", "nvidia/nemotron-nano-vl-8b-v1").strip()


async def nim_chat(
    messages: list[dict[str, Any]],
    *,
    model: str | None = None,
    image_b64: str | None = None,
    max_tokens: int = 1024,
) -> str:
    key = _api_key()
    if not key:
        raise RuntimeError("NIM_API_KEY not set")

    msgs = [dict(m) for m in messages]
    if image_b64:
        raw = image_b64.split(",", 1)[-1] if "," in image_b64 else image_b64
        if msgs:
            last = msgs[-1]
            content = last.get("content")
            if isinstance(content, str):
                last["content"] = [
                    {"type": "text", "text": content},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{raw}"}},
                ]

    payload = {
        "model": model or (_vision_model() if image_b64 else _default_model()),
        "messages": msgs,
        "max_tokens": max_tokens,
        "temperature": 0.4,
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        res = await client.post(
            f"{_base_url()}/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json=payload,
        )
        res.raise_for_status()
        data = res.json()
    choices = data.get("choices") or []
    if not choices:
        return ""
    msg = choices[0].get("message") or {}
    return (msg.get("content") or "").strip()


def _parse_json_blob(text: str) -> dict:
    text = text.strip()
    if text.startswith("{"):
        return json.loads(text)
    match = _JSON_BLOCK.search(text)
    if match:
        return json.loads(match.group())
    raise ValueError("No JSON object in NIM response")


async def nim_chat_json(
    messages: list[dict[str, Any]],
    *,
    model: str | None = None,
    image_b64: str | None = None,
) -> dict:
    raw = await nim_chat(messages, model=model, image_b64=image_b64)
    return _parse_json_blob(raw)


async def nim_vision_latex(image_b64: str) -> str:
    """Teacher label for handwriting correction path."""
    out = await nim_chat(
        [
            {
                "role": "user",
                "content": (
                    "Read the handwritten math in this image. "
                    "Reply with only the LaTeX for the expression, no prose."
                ),
            }
        ],
        model=_vision_model(),
        image_b64=image_b64,
        max_tokens=256,
    )
    return out.strip().strip("$").strip()


def nim_vision_latex_sync(image_b64: str) -> str:
    """Sync wrapper for OCR tier (used from recognize_canvas)."""
    import asyncio
    import concurrent.futures

    def _run() -> str:
        return asyncio.run(nim_vision_latex(image_b64))

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return _run()
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(_run).result()
