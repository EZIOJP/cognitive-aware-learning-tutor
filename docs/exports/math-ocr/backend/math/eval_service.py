"""Lightweight SymPy expression evaluation for dashboard calculator widget."""

from __future__ import annotations

import re

import sympy as sp
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

_TRANSFORMATIONS = standard_transformations + (implicit_multiplication_application, convert_xor)


def _normalize(expr: str) -> str:
    s = expr.strip()
    s = s.replace("^", "**")
    s = re.sub(r"\bintegrate\b", "integrate", s, flags=re.I)
    s = re.sub(r"\bdiff\b", "diff", s, flags=re.I)
    return s


def eval_expression(expression: str) -> dict:
    raw = _normalize(expression)
    if not raw:
        raise ValueError("Expression is empty")

    steps: list[str] = [f"Input: {expression.strip()}"]

    lowered = raw.lower()
    x = sp.Symbol("x")

    try:
        if lowered.startswith("integrate("):
            inner = raw[len("integrate(") :].rstrip(")")
            if "," in inner:
                body, var_part = inner.rsplit(",", 1)
                var_name = var_part.strip()
                sym = sp.Symbol(var_name) if var_name else x
            else:
                body, sym = inner, x
            expr = parse_expr(body.strip(), transformations=_TRANSFORMATIONS)
            result = sp.integrate(expr, sym)
            steps.append(f"Integrate {sp.latex(expr)} d{sym}")
        elif lowered.startswith("diff("):
            inner = raw[len("diff(") :].rstrip(")")
            if "," in inner:
                body, var_part = inner.rsplit(",", 1)
                sym = sp.Symbol(var_part.strip()) if var_part.strip() else x
            else:
                body, sym = inner, x
            expr = parse_expr(body.strip(), transformations=_TRANSFORMATIONS)
            result = sp.diff(expr, sym)
            steps.append(f"d/d{sym} ({sp.latex(expr)})")
        elif lowered.startswith("solve("):
            inner = raw[len("solve(") :].rstrip(")")
            if "," in inner:
                eq_part, var_part = inner.rsplit(",", 1)
                sym = sp.Symbol(var_part.strip()) if var_part.strip() else x
            else:
                eq_part, sym = inner, x
            if "=" in eq_part:
                left, right = eq_part.split("=", 1)
                eq = sp.Eq(
                    parse_expr(left.strip(), transformations=_TRANSFORMATIONS),
                    parse_expr(right.strip(), transformations=_TRANSFORMATIONS),
                )
            else:
                eq = parse_expr(eq_part.strip(), transformations=_TRANSFORMATIONS)
            solutions = sp.solve(eq, sym)
            result = solutions if isinstance(solutions, list) else [solutions]
            steps.append(f"Solve for {sym}")
        elif lowered.startswith("simplify("):
            inner = raw[len("simplify(") :].rstrip(")")
            expr = parse_expr(inner.strip(), transformations=_TRANSFORMATIONS)
            result = sp.simplify(expr)
            steps.append("Simplify")
        else:
            expr = parse_expr(raw, transformations=_TRANSFORMATIONS)
            simplified = sp.simplify(expr)
            result = simplified
            if simplified != expr:
                steps.append("Simplified")
    except Exception as e:
        raise ValueError(f"Could not parse expression: {e}") from e

    latex = sp.latex(result)
    text = sp.sstr(result)
    steps.append(f"= {text}")

    return {
        "result": text,
        "latex": latex,
        "steps": steps,
        "ok": True,
    }
