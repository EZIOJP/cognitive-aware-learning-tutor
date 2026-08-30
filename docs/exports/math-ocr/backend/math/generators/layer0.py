"""Layer-0 procedural generators — dynamic mental-math curriculum (SymPy ground truth)."""

from __future__ import annotations

import random
import re
import uuid
from typing import Any

import sympy as sp


def _base(
    topic: str,
    skill_id: str,
    prompt: str,
    answer: Any,
    *,
    hint: str = "",
    mode: str = "",
    factors: list[int] | None = None,
    difficulty: str = "easy",
) -> dict[str, Any]:
    ans = str(answer)
    tags = [skill_id]
    if mode:
        tags.append(mode)
    return {
        "generated_id": str(uuid.uuid4()),
        "question_id": None,
        "template_id": None,
        "title": skill_id,
        "topic": topic,
        "skill_id": skill_id,
        "operation": "generated",
        "prompt": prompt,
        "latex": "",
        "expected_answer": ans,
        "points": 10,
        "explanation": hint,
        "sympy_enabled": True,
        "source": "skill_generator",
        "difficulty": difficulty,
        "tags": tags,
        "mode": mode,
        "factors": factors or [],
    }


def _exclude_set(params: dict[str, Any]) -> set[int]:
    raw = params.get("exclude_factors") or params.get("exclude") or [1, 2, 10]
    return {int(x) for x in raw}


def _pick_int(lo: int, hi: int, *, exclude: set[int], bias: list[int] | None = None) -> int:
    pool = [n for n in range(lo, hi + 1) if n not in exclude]
    if not pool:
        pool = list(range(lo, hi + 1))
    if bias:
        weighted: list[int] = []
        for n in pool:
            w = 1 + (3 if n in bias else 0)
            weighted.extend([n] * w)
        return random.choice(weighted)
    return random.choice(pool)


def times_strategy_hint(a: int, b: int) -> str:
    """Mental strategy tip for a×b (shown on miss / as explanation)."""
    x, y = (a, b) if a <= b else (b, a)
    if x == y:
        return f"Square: {x}². Nearby: {x - 1}×{x + 1} = {x}² − 1."
    # near 10
    for base in (10, 20, 30, 40, 50, 100):
        if abs(a - base) <= 2 and a != base:
            d = a - base
            sign = "+" if d > 0 else "−"
            return (
                f"Near {base}: {a}×{b} = {base}×{b} {sign} {abs(d)}×{b} "
                f"= {base * b} {sign} {abs(d) * b}."
            )
        if abs(b - base) <= 2 and b != base:
            d = b - base
            sign = "+" if d > 0 else "−"
            return (
                f"Near {base}: {a}×{b} = {a}×{base} {sign} {a}×{abs(d)} "
                f"= {a * base} {sign} {a * abs(d)}."
            )
    # split larger factor
    if y >= 12:
        tens = (y // 10) * 10
        ones = y - tens
        if tens and ones:
            return (
                f"Split: {x}×{y} = {x}×{tens} + {x}×{ones} "
                f"= {x * tens} + {x * ones} = {x * y}."
            )
    return f"Break it down: {a}×{b} = {a * b}. Practice this pair until it feels automatic."


def gen_times_tables(
    skill_id: str,
    topic: str,
    params: dict[str, Any],
    *,
    bias_factors: list[int] | None = None,
) -> dict[str, Any]:
    a_min = int(params.get("a_min", 3))
    a_max = int(params.get("a_max", 20))
    b_min = int(params.get("b_min", 3))
    b_max = int(params.get("b_max", 20))
    exclude = _exclude_set(params)
    bias = list(bias_factors or []) + list(params.get("bias_factors") or [])
    a = _pick_int(a_min, a_max, exclude=exclude, bias=bias)
    b = _pick_int(b_min, b_max, exclude=exclude, bias=bias)
    answer = int(sp.Integer(a) * sp.Integer(b))
    return _base(
        topic,
        skill_id,
        f"What is {a} × {b}?",
        answer,
        hint=times_strategy_hint(a, b),
        mode="forward",
        factors=[a, b],
    )


def gen_mental_shortcuts(
    skill_id: str,
    topic: str,
    params: dict[str, Any],
    *,
    bias_factors: list[int] | None = None,
) -> dict[str, Any]:
    """Near-10 / split products — always attach strategy hint."""
    exclude = _exclude_set(params)
    mode = random.choice(["near10", "near20", "split"])
    if mode == "near10":
        a = random.choice([9, 11, 19, 21, 29, 31])
        b = _pick_int(3, 12, exclude=exclude, bias=bias_factors)
    elif mode == "near20":
        a = random.choice([18, 19, 21, 22])
        b = _pick_int(3, 12, exclude=exclude, bias=bias_factors)
    else:
        a = _pick_int(6, 15, exclude=exclude, bias=bias_factors)
        b = random.choice([14, 15, 16, 17, 18, 19, 24, 25])
    answer = a * b
    return _base(
        topic,
        skill_id,
        f"What is {a} × {b}? (use a shortcut)",
        answer,
        hint=times_strategy_hint(a, b),
        mode="shortcut",
        factors=[a, b],
        difficulty="medium",
    )


def gen_times_estimation(
    skill_id: str,
    topic: str,
    params: dict[str, Any],
    *,
    bias_factors: list[int] | None = None,
) -> dict[str, Any]:
    exclude = _exclude_set(params)
    a = _pick_int(11, 49, exclude=exclude | {10}, bias=bias_factors)
    b = _pick_int(6, 19, exclude=exclude | {10}, bias=bias_factors)
    exact = a * b
    # Build 3 plausible round estimates; correct = closest to exact among options
    round_a = int(round(a / 10) * 10) or 10
    round_b = int(round(b / 10) * 10) or 10
    mid = round_a * round_b
    opts = sorted({mid, mid - round_b * 10, mid + round_b * 10, exact // 100 * 100 or 100})
    opts = [o for o in opts if o > 0][:3]
    while len(opts) < 3:
        opts.append(opts[-1] + 100)
    # Answer is the option closest to exact
    best = min(opts, key=lambda o: abs(o - exact))
    prompt = (
        f"Estimate {a} × {b}. Which is closest: "
        f"{opts[0]}, {opts[1]}, or {opts[2]}? (enter the number)"
    )
    hint = f"Exact is {exact}. Round to {round_a}×{round_b} ≈ {mid}, then pick closest."
    return _base(
        topic,
        skill_id,
        prompt,
        best,
        hint=hint,
        mode="estimate",
        factors=[a, b],
        difficulty="medium",
    )


def gen_times_reverse(
    skill_id: str,
    topic: str,
    params: dict[str, Any],
    *,
    bias_factors: list[int] | None = None,
) -> dict[str, Any]:
    exclude = _exclude_set(params)
    a_min = int(params.get("a_min", 3))
    a_max = int(params.get("a_max", 20))
    b_min = int(params.get("b_min", 3))
    b_max = int(params.get("b_max", 12))
    a = _pick_int(a_min, a_max, exclude=exclude, bias=bias_factors)
    b = _pick_int(b_min, b_max, exclude=exclude, bias=bias_factors)
    product = a * b
    if random.choice([True, False]):
        prompt = f"What number × {b} = {product}?"
        answer = a
    else:
        prompt = f"{a} × ? = {product}"
        answer = b
    return _base(
        topic,
        skill_id,
        prompt,
        answer,
        hint=f"Division: {product} ÷ known factor. Also {a}×{b}={product}.",
        mode="reverse",
        factors=[a, b],
    )


def gen_times_fact_family(
    skill_id: str,
    topic: str,
    params: dict[str, Any],
    *,
    bias_factors: list[int] | None = None,
) -> dict[str, Any]:
    exclude = _exclude_set(params)
    a = _pick_int(3, 12, exclude=exclude, bias=bias_factors)
    b = _pick_int(3, 12, exclude=exclude, bias=bias_factors)
    product = a * b
    mode = random.choice(["mul", "div_a", "div_b"])
    if mode == "mul":
        prompt = f"Fact family: what is {a} × {b}?"
        answer = product
    elif mode == "div_a":
        prompt = f"Fact family: what is {product} ÷ {a}?"
        answer = b
    else:
        prompt = f"Fact family: what is {product} ÷ {b}?"
        answer = a
    hint = f"Family: {a}×{b}={product}, {product}÷{a}={b}, {product}÷{b}={a}."
    return _base(
        topic,
        skill_id,
        prompt,
        answer,
        hint=hint,
        mode="family",
        factors=[a, b],
    )


def gen_powers(
    skill_id: str,
    topic: str,
    params: dict[str, Any],
    *,
    bias_factors: list[int] | None = None,
) -> dict[str, Any]:
    exp = int(params.get("exponent") or params.get("exp") or 2)
    base_min = int(params.get("base_min", 2))
    base_max = int(params.get("base_max", 10))
    important = params.get("important_bases")
    exclude = _exclude_set({**params, "exclude_factors": params.get("exclude_factors") or []})
    # For squares, allowing 1 is ok sometimes — but curriculum said squares up to 50; 1² is trivial
    if important:
        pool = [int(x) for x in important]
    else:
        pool = [n for n in range(base_min, base_max + 1) if n not in exclude]
        if not pool:
            pool = list(range(base_min, base_max + 1))
    if bias_factors:
        weighted: list[int] = []
        for n in pool:
            w = 1 + (4 if n in bias_factors else 0)
            weighted.extend([n] * w)
        base = random.choice(weighted)
    else:
        base = random.choice(pool)
    answer = int(sp.Integer(base) ** sp.Integer(exp))
    if exp == 2:
        prompt = f"What is {base}²?"
        hint = f"{base}×{base}={answer}." + (
            f" Nearby: ({base}-1)×({base}+1)={base * base - 1}." if base > 1 else ""
        )
    elif exp == 3:
        prompt = f"What is {base}³?"
        hint = f"{base}²={base * base}, then ×{base}={answer}."
    else:
        prompt = f"What is {base}^{exp}?"
        hint = f"Compute stepwise: {base}^{exp} = {answer}."
    return _base(
        topic,
        skill_id,
        prompt,
        answer,
        hint=hint,
        mode=f"power{exp}",
        factors=[base, exp],
        difficulty="medium" if exp >= 3 else "easy",
    )


def gen_powers_mixed(
    skill_id: str,
    topic: str,
    params: dict[str, Any],
    *,
    bias_factors: list[int] | None = None,
) -> dict[str, Any]:
    exp_min = int(params.get("exp_min", 2))
    exp_max = int(params.get("exp_max", 6))
    exp = random.randint(exp_min, exp_max)
    # bases below 10
    p = {
        **params,
        "exponent": exp,
        "base_min": int(params.get("base_min", 2)),
        "base_max": int(params.get("base_max", 9)),
    }
    return gen_powers(skill_id, topic, p, bias_factors=bias_factors)


def gen_division_facts(
    skill_id: str,
    topic: str,
    params: dict[str, Any],
    *,
    bias_factors: list[int] | None = None,
) -> dict[str, Any]:
    max_d = int(params.get("max_divisor", 12))
    max_q = int(params.get("max_quotient", 20))
    exclude = _exclude_set(params)
    d = _pick_int(2, max_d, exclude=exclude | {1}, bias=bias_factors)
    q = _pick_int(2, max_q, exclude={1}, bias=bias_factors)
    dividend = int(sp.Integer(d) * sp.Integer(q))
    return _base(
        topic,
        skill_id,
        f"What is {dividend} ÷ {d}?",
        q,
        hint=f"Think: ? × {d} = {dividend}. Also {d}×{q}={dividend}.",
        mode="division",
        factors=[d, q],
    )


def gen_divisibility_rules(
    skill_id: str,
    topic: str,
    params: dict[str, Any],
    *,
    bias_factors: list[int] | None = None,
) -> dict[str, Any]:
    rules = [2, 3, 4, 5, 6, 8, 9, 10, 11]
    d = random.choice(rules)
    make_yes = random.choice([True, False])
    if make_yes:
        n = d * random.randint(11, 99)
    else:
        n = d * random.randint(11, 99) + random.randint(1, d - 1)
    expected = "yes" if (n % d == 0) else "no"
    return _base(
        topic,
        skill_id,
        f"Is {n} divisible by {d}? Answer yes or no.",
        expected,
        hint=f"Use the divisibility rule for {d}.",
        mode="divisibility",
    )


def gen_lcm_gcd(
    skill_id: str,
    topic: str,
    params: dict[str, Any],
    *,
    bias_factors: list[int] | None = None,
) -> dict[str, Any]:
    max_n = int(params.get("max_n", 60))
    a = random.randint(6, max_n)
    b = random.randint(6, max_n)
    if random.choice([True, False]):
        ans = int(sp.gcd(a, b))
        return _base(topic, skill_id, f"What is gcd({a}, {b})?", ans, mode="gcd")
    ans = int(sp.lcm(a, b))
    return _base(topic, skill_id, f"What is lcm({a}, {b})?", ans, mode="lcm")


def gen_fractions_ops(
    skill_id: str,
    topic: str,
    params: dict[str, Any],
    *,
    bias_factors: list[int] | None = None,
) -> dict[str, Any]:
    max_den = int(params.get("max_den", 12))
    op = random.choice(["+", "-", "*", "/"])
    a_n, a_d = random.randint(1, max_den - 1), random.randint(2, max_den)
    b_n, b_d = random.randint(1, max_den - 1), random.randint(2, max_den)
    a = sp.Rational(a_n, a_d)
    b = sp.Rational(b_n, b_d)
    if op == "+":
        ans = sp.simplify(a + b)
        prompt = f"Compute {a_n}/{a_d} + {b_n}/{b_d} (simplified)."
    elif op == "-":
        ans = sp.simplify(a - b)
        prompt = f"Compute {a_n}/{a_d} - {b_n}/{b_d} (simplified)."
    elif op == "*":
        ans = sp.simplify(a * b)
        prompt = f"Compute {a_n}/{a_d} × {b_n}/{b_d} (simplified)."
    else:
        if b == 0:
            b = sp.Rational(1, 2)
            b_n, b_d = 1, 2
        ans = sp.simplify(a / b)
        prompt = f"Compute {a_n}/{a_d} ÷ {b_n}/{b_d} (simplified)."
    return _base(topic, skill_id, prompt, ans, mode="fractions")


def gen_decimal_fraction_percent(
    skill_id: str,
    topic: str,
    params: dict[str, Any],
    *,
    bias_factors: list[int] | None = None,
) -> dict[str, Any]:
    mode = random.choice(["pct_to_frac", "frac_to_pct", "dec_to_pct"])
    if mode == "pct_to_frac":
        pct = random.choice([10, 20, 25, 40, 50, 75])
        ans = sp.simplify(sp.Rational(pct, 100))
        return _base(topic, skill_id, f"Express {pct}% as a simplified fraction.", ans, mode="pct")
    if mode == "frac_to_pct":
        frac = random.choice(
            [sp.Rational(1, 2), sp.Rational(1, 4), sp.Rational(3, 4), sp.Rational(1, 5)]
        )
        ans = int(frac * 100)
        return _base(
            topic,
            skill_id,
            f"Express {frac} as a percent (number only, e.g. 50).",
            ans,
            mode="pct",
        )
    dec = random.choice(["0.2", "0.25", "0.5", "0.75", "0.1"])
    ans = int(sp.Rational(dec) * 100)
    return _base(topic, skill_id, f"Express {dec} as a percent (number only).", ans, mode="pct")


def gen_daily_mixed(
    skill_id: str,
    topic: str,
    params: dict[str, Any],
    *,
    bias_factors: list[int] | None = None,
) -> dict[str, Any]:
    """One item from a rotating mix — caller builds a 5-pack via generate_drill_items."""
    roll = random.random()
    if roll < 0.45:
        return gen_times_tables(
            skill_id,
            topic,
            {"a_min": 3, "a_max": 20, "b_min": 3, "b_max": 20, "exclude_factors": [1, 2, 10]},
            bias_factors=bias_factors,
        )
    if roll < 0.65:
        return gen_powers(
            skill_id,
            topic,
            {"exponent": 2, "base_min": 2, "base_max": 25, "exclude_factors": [1]},
            bias_factors=bias_factors,
        )
    if roll < 0.8:
        return gen_times_reverse(
            skill_id,
            topic,
            {"a_min": 3, "a_max": 12, "b_min": 3, "b_max": 12, "exclude_factors": [1, 2, 10]},
            bias_factors=bias_factors,
        )
    return gen_mental_shortcuts(
        skill_id,
        topic,
        {"exclude_factors": [1, 2, 10]},
        bias_factors=bias_factors,
    )


GENERATORS = {
    "times_tables": gen_times_tables,
    "mental_shortcuts": gen_mental_shortcuts,
    "times_estimation": gen_times_estimation,
    "times_reverse": gen_times_reverse,
    "times_fact_family": gen_times_fact_family,
    "powers": gen_powers,
    "powers_mixed": gen_powers_mixed,
    "daily_mixed": gen_daily_mixed,
    "division_facts": gen_division_facts,
    "divisibility_rules": gen_divisibility_rules,
    "lcm_gcd": gen_lcm_gcd,
    "fractions_ops": gen_fractions_ops,
    "decimal_fraction_percent": gen_decimal_fraction_percent,
}


_TIMES_RE = re.compile(r"(\d+)\s*[×x*]\s*(\d+)")
_POW_RE = re.compile(r"(\d+)\s*[²2]|(\d+)\s*\^\s*(\d+)|(\d+)³")


def parse_factors_from_prompt(prompt: str) -> list[int]:
    """Extract factors/bases from a generated prompt for adaptive weighting."""
    text = prompt or ""
    m = _TIMES_RE.search(text)
    if m:
        return [int(m.group(1)), int(m.group(2))]
    # n²
    m2 = re.search(r"(\d+)²", text)
    if m2:
        return [int(m2.group(1))]
    m3 = re.search(r"(\d+)³", text)
    if m3:
        return [int(m3.group(1))]
    mp = re.search(r"(\d+)\s*\^\s*(\d+)", text)
    if mp:
        return [int(mp.group(1))]
    # reverse: "What number × 7 = 56" or "8 × ? = 56"
    mr = re.search(r"[×x*]\s*(\d+)\s*=\s*(\d+)", text)
    if mr:
        return [int(mr.group(1))]
    mr2 = re.search(r"(\d+)\s*[×x*]\s*\?", text)
    if mr2:
        return [int(mr2.group(1))]
    md = re.search(r"(\d+)\s*÷\s*(\d+)", text)
    if md:
        return [int(md.group(2))]
    return []


def generate_for_node(
    node: dict[str, Any],
    *,
    bias_factors: list[int] | None = None,
) -> dict[str, Any]:
    key = str(node.get("generator") or "")
    fn = GENERATORS.get(key)
    if not fn:
        raise ValueError(f"Unknown generator: {key}")
    return fn(
        str(node["id"]),
        str(node.get("topic") or "Arithmetic"),
        dict(node.get("params") or {}),
        bias_factors=bias_factors,
    )
