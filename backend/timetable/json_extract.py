"""Extract JSON objects from messy text (markdown fences, LLM chatter, etc.)."""

from __future__ import annotations

import json
import re
from typing import Any


def _strip_noise(text: str) -> str:
    text = text.strip().lstrip("\ufeff")
    # Markdown code fence
    fence = re.search(r"```(?:json|JSON)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    # Leading/trailing prose before first { or [
    return text


def _find_json_span(text: str) -> str | None:
    """Return substring that balances outermost { } or [ ]."""
    text = _strip_noise(text)
    starts = [(text.find("{"), "{"), (text.find("["), "[")]
    starts = [(i, ch) for i, ch in starts if i >= 0]
    if not starts:
        return None
    start_idx, open_ch = min(starts, key=lambda x: x[0])
    close_ch = "}" if open_ch == "{" else "]"
    depth = 0
    in_string = False
    escape = False
    for i in range(start_idx, len(text)):
        c = text[i]
        if escape:
            escape = False
            continue
        if c == "\\" and in_string:
            escape = True
            continue
        if c == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if c == open_ch:
            depth += 1
        elif c == close_ch:
            depth -= 1
            if depth == 0:
                return text[start_idx : i + 1]
    return None


def extract_json_from_text(text: str) -> Any:
    """
    Parse JSON from raw text. Raises ValueError with a helpful message on failure.
    """
    if not text or not text.strip():
        raise ValueError("Empty input")

    span = _find_json_span(text)
    candidates: list[str] = []
    if span:
        candidates.append(span)
    candidates.append(_strip_noise(text))

    last_err: Exception | None = None
    for raw in candidates:
        for cleaned in (raw, _remove_trailing_commas(raw)):
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError as exc:
                last_err = exc
                continue

    raise ValueError(f"Could not parse JSON: {last_err}")


def _remove_trailing_commas(s: str) -> str:
    """Remove trailing commas before } or ] — common in hand-edited JSON."""
    return re.sub(r",\s*([}\]])", r"\1", s)
