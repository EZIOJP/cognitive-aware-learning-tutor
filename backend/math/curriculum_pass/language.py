from __future__ import annotations

import re

from backend.math.curriculum_pass.constants import EN_HEURISTIC_MIN_CHARS

_LETTER = re.compile(r"[^\W\d_]", re.UNICODE)
_LATIN = re.compile(r"[A-Za-z]")


def decide_english(problem: str, *, language_field: str | None) -> tuple[bool, str]:
    lang = (language_field or "").strip().lower()
    if lang:
        if lang in ("en", "english"):
            return True, "explicit_en"
        return False, "explicit_non_en"
    text = problem or ""
    compact = "".join(text.split())
    if len(compact) < EN_HEURISTIC_MIN_CHARS:
        return True, "short_keep"
    letters = _LETTER.findall(text)
    if not letters:
        return True, "script_keep"
    latin = sum(1 for ch in letters if _LATIN.match(ch))
    non_latin_ratio = 1.0 - (latin / len(letters))
    if non_latin_ratio > 0.30:
        return False, "script_drop"
    return True, "script_keep"
