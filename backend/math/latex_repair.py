"""Mathpix-style deterministic LaTeX micro-repairs (Phase 3)."""

from __future__ import annotations

import re

# Common OCR hallucinations → likely fixes (syntax only)
_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\\int\s+([a-zA-Z])\s+d\s+\+"), r"\\int \1 dx"),
    (re.compile(r"\\int\s+([a-zA-Z])\s+d\s*([^+\s])"), r"\\int \1 d\2"),
    (re.compile(r"\\left\s*\\right"), ""),
    (re.compile(r"\{\s*\}"), ""),
    (re.compile(r"\\cdot\s*\\cdot"), r"\\cdot"),
    (re.compile(r"\s+"), " "),
]


def repair_latex(latex: str) -> str:
    text = (latex or "").strip()
    if not text:
        return text
    for pattern, repl in _RULES:
        text = pattern.sub(repl, text)
    return text.strip()
