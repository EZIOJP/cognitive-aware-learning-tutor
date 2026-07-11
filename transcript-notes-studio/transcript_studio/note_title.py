"""LLM-assisted note title / filename slug for classic auto pipeline."""

from __future__ import annotations

import re
from typing import Callable

GenerateFn = Callable[[str], str | None]

_TITLE_PROMPT = """You name a lecture notes file from this cleaned transcript excerpt.

Rules:
- Reply with ONE short title only (3–8 words).
- Topic of the lecture (e.g. "NumPy arrays and DAV intro"), not "live captions" or a date.
- No quotes, no markdown, no explanation.

Excerpt:
{excerpt}
"""


def _slugify(title: str) -> str:
    text = (title or "").strip()
    text = re.sub(r"[\"'`*_#]+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    # Take first line only
    text = text.splitlines()[0].strip() if text else ""
    safe = "".join(c if c.isalnum() or c in "-_ " else "" for c in text)
    safe = re.sub(r"\s+", "_", safe).strip("_")
    return (safe[:60] or "lecture").lower()


def suggest_note_title(
    cleaned_transcript: str,
    *,
    generate_fn: GenerateFn,
    fallback: str = "lecture",
) -> tuple[str, str]:
    """
    Return (display_title, filename_slug) from LLM, with safe fallback.
    """
    excerpt = re.sub(r"\s+", " ", (cleaned_transcript or "").strip())[:3500]
    if not excerpt:
        slug = _slugify(fallback)
        return fallback.replace("_", " "), slug

    raw = generate_fn(_TITLE_PROMPT.format(excerpt=excerpt))
    if not raw or not raw.strip():
        slug = _slugify(fallback)
        return fallback.replace("_", " "), slug

    display = raw.strip().splitlines()[0].strip().strip("\"'")
    display = re.sub(r"^#+\s*", "", display)
    if len(display) < 3 or len(display) > 120:
        display = fallback.replace("_", " ")
    slug = _slugify(display)
    return display, slug
