"""SymPy-triggered re-OCR repair loop (Phase 2)."""

from __future__ import annotations

from dataclasses import dataclass

from backend.math.latex_repair import repair_latex
from backend.math.latex_validate import latex_structure_valid


def sympy_parseable(latex: str) -> tuple[bool, str]:
    """True when SymPy can parse (or expression is plain arithmetic)."""
    text = (latex or "").strip()
    if not text:
        return False, "empty"
    ok, reason = latex_structure_valid(text)
    if not ok:
        return False, reason
    if re_fullmatch_arith(text):
        return True, "arith"
    try:
        from sympy.parsing.latex import parse_latex

        parse_latex(text)
        return True, "sympy"
    except Exception:
        pass
    try:
        import sympy

        expr = text
        for tok in (r"\cdot", r"\times", r"\div"):
            expr = expr.replace(tok, "*")
        expr = expr.replace("^", "**")
        sympy.sympify(expr)
        return True, "sympy_simple"
    except Exception as e:
        return False, str(e)[:80]


def re_fullmatch_arith(text: str) -> bool:
    import re

    return bool(re.fullmatch(r"[\d\s.+\-*/=()^]+", text.replace(" ", "")))


@dataclass
class RepairResult:
    latex: str
    confidence: float
    source: str
    repaired: bool
    repair_reason: str = ""


def apply_repair_pipeline(
    latex: str,
    confidence: float,
    source: str,
    *,
    alternate_latex: str | None = None,
    alternate_confidence: float = 0.0,
    alternate_source: str = "",
) -> RepairResult:
    """
    1. Rule-based latex repair
    2. If still invalid and alternate engine disagrees → try alternate
    3. Return best parseable result
    """
    fixed = repair_latex(latex)
    ok, reason = sympy_parseable(fixed)
    if ok:
        boost = 0.08 if fixed != latex else 0.0
        return RepairResult(
            latex=fixed,
            confidence=min(1.0, confidence + boost),
            source=source,
            repaired=fixed != latex,
            repair_reason="rule_repair" if fixed != latex else "",
        )

    if alternate_latex and alternate_latex.strip():
        alt_fixed = repair_latex(alternate_latex)
        alt_ok, alt_reason = sympy_parseable(alt_fixed)
        if alt_ok:
            return RepairResult(
                latex=alt_fixed,
                confidence=max(alternate_confidence, confidence * 0.9),
                source=alternate_source or "alternate_engine",
                repaired=True,
                repair_reason=f"alternate_engine:{reason}",
            )

    return RepairResult(
        latex=fixed,
        confidence=confidence * 0.85,
        source=source,
        repaired=fixed != latex,
        repair_reason=f"unparsed:{reason}",
    )
