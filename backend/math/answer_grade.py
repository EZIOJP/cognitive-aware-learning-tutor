"""SymPy-backed answer equivalence for math free-text grading."""

from __future__ import annotations

import re
from typing import Any

import sympy as sp
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

_TRANSFORMATIONS = standard_transformations + (implicit_multiplication_application, convert_xor)


def _strip_latex_wrappers(raw: str) -> str:
    """Light cleanup so OCR LaTeX can feed SymPy / string compare."""
    s = (raw or "").strip()
    if not s:
        return s
    s = re.sub(r"^\$+|\$+$", "", s)
    s = re.sub(r"\\left|\\right", "", s)
    s = re.sub(r"\\times", "*", s, flags=re.I)
    s = re.sub(r"\\div", "/", s, flags=re.I)
    s = re.sub(r"\\cdot", "*", s, flags=re.I)
    s = re.sub(r"\\frac\s*\{([^{}]+)\}\s*\{([^{}]+)\}", r"(\1)/(\2)", s)
    s = re.sub(r"\\sqrt\s*\{([^{}]+)\}", r"sqrt(\1)", s)
    s = s.replace("{", "").replace("}", "")
    return s.strip()


def _normalize_string(text: str) -> str:
    s = _strip_latex_wrappers(text or "").strip().lower()
    s = s.replace("×", "*").replace("÷", "/")
    s = re.sub(r"\s+", "", s)
    return s


def _prep_for_sympy(raw: str) -> str:
    s = _strip_latex_wrappers(raw or "").strip()
    if not s:
        return s
    # Percent → fraction: 50% → (50)/100
    if s.endswith("%"):
        inner = s[:-1].strip()
        if inner:
            return f"({inner})/100"
    s = s.replace("^", "**")
    s = s.replace("×", "*").replace("÷", "/")
    return s


def _to_expr(raw: str) -> Any | None:
    prepared = _prep_for_sympy(raw)
    if not prepared:
        return None
    try:
        return parse_expr(prepared, transformations=_TRANSFORMATIONS)
    except Exception:
        try:
            return sp.sympify(prepared)
        except Exception:
            return None


def answers_equivalent(expected: str, user_input: str, *, tolerance: float = 1e-9) -> bool:
    """
    Return True if user_input matches expected under string normalize or SymPy equivalence.

    Handles fractions vs decimals, commutative sums/products, and simple percents.
    Malformed input → False (do not raise).
    """
    exp_s = _normalize_string(expected)
    usr_s = _normalize_string(user_input)
    if exp_s and exp_s == usr_s:
        return True
    # yes/no aliases
    yn = {"yes": {"yes", "y", "true", "1"}, "no": {"no", "n", "false", "0"}}
    if exp_s in yn and usr_s in yn[exp_s]:
        return True

    exp_e = _to_expr(expected)
    usr_e = _to_expr(user_input)
    if exp_e is None or usr_e is None:
        return False

    try:
        diff = sp.simplify(sp.together(exp_e - usr_e))
        if diff == 0:
            return True
        if getattr(diff, "is_number", False):
            return abs(complex(diff.evalf())) < tolerance
        if diff is True or diff == sp.true:
            return True
        return bool(sp.Eq(exp_e, usr_e) == True)  # noqa: E712
    except Exception:
        return False
