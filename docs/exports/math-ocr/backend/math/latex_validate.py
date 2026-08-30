"""TAMER-lite LaTeX bracket / structure validators (Phase 3)."""

from __future__ import annotations

import re


def bracket_balance_ok(latex: str) -> bool:
    text = latex or ""
    pairs = {"(": ")", "{": "}", "[": "]"}
    stack: list[str] = []
    escaped = False
    for ch in text:
        if escaped:
            escaped = False
            continue
        if ch == "\\":
            escaped = True
            continue
        if ch in pairs:
            stack.append(pairs[ch])
        elif ch in pairs.values():
            if not stack or stack.pop() != ch:
                return False
    return len(stack) == 0


_FRAC_RE = re.compile(r"\\frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}")


def frac_well_formed(latex: str) -> bool:
    text = latex or ""
    if "\\frac" not in text and "\\tfrac" not in text and "\\dfrac" not in text:
        return True
    for m in _FRAC_RE.finditer(text):
        if not m.group(1).strip() or not m.group(2).strip():
            return False
    if re.search(r"\\frac\s*\{\s*\}|\{\\frac\s*$", text):
        return False
    return True


def latex_structure_valid(latex: str) -> tuple[bool, str]:
    """Return (ok, reason). Syntax-only — does not grade math correctness."""
    if not (latex or "").strip():
        return False, "empty"
    if not bracket_balance_ok(latex):
        return False, "bracket_mismatch"
    if not frac_well_formed(latex):
        return False, "malformed_frac"
    return True, "ok"
