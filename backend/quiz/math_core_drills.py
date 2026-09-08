"""Math Core worksheet drills — chunked fluency with coverage bias.

MT0-T01…T09 (and legacy MT1-T16…T24) get on-demand questions that:
  • cover the worksheet number space (tables, squares, cubes, …)
  • prefer facts not yet practiced correctly for this user
  • still mix in ~30% practiced facts for retention
  • start short; Keep going appends another chunk (Math Core only)
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from backend.paths import ROOT
from backend.quiz import math_core as mc

_COVERAGE_PATH = ROOT / "data" / "quiz" / "math_core_coverage.json"

# Soft floor: still allow Keep going with review mix when fewer left.
_KEEP_GOING_MIN_REMAINING = 1


@dataclass(frozen=True)
class Fact:
    key: str
    prompt: str
    answer: str
    speed_kind: str = "math.fluency"


def _coverage_store() -> dict[str, Any]:
    try:
        if _COVERAGE_PATH.is_file():
            raw = json.loads(_COVERAGE_PATH.read_text(encoding="utf-8"))
            return raw if isinstance(raw, dict) else {}
    except Exception:
        pass
    return {}


def _save_coverage(data: dict[str, Any]) -> None:
    _COVERAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _COVERAGE_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def practiced_keys(user_id: int, tag: str) -> set[str]:
    t = mc.canonical_tag(tag) or (tag or "").strip().upper()
    store = _coverage_store()
    u = store.get(str(int(user_id))) or {}
    keys = u.get(t) or []
    return {str(k) for k in keys if str(k).strip()}


def mark_practiced(user_id: int, tag: str, keys: list[str]) -> None:
    """Record fact keys as proficient (call only on correct answers)."""
    t = mc.canonical_tag(tag) or (tag or "").strip().upper()
    if not t or not keys:
        return
    store = _coverage_store()
    uid = str(int(user_id))
    u = store.setdefault(uid, {})
    have = set(str(k) for k in (u.get(t) or []) if str(k).strip())
    have.update(str(k) for k in keys if str(k).strip())
    u[t] = sorted(have)
    store[uid] = u
    _save_coverage(store)


def coverage_stats(user_id: int, tag: str) -> dict[str, Any]:
    t = mc.canonical_tag(tag) or (tag or "").strip().upper()
    universe = universe_for_tag(t)
    total = len(universe)
    practiced = practiced_keys(int(user_id), t) if user_id is not None else set()
    done = len(practiced & {f.key for f in universe}) if universe else 0
    remaining = max(0, total - done)
    pct = round(100.0 * done / total, 1) if total else 0.0
    return {
        "tag": t,
        "label": mc.label_for_tag(t),
        "practiced": done,
        "total": total,
        "remaining": remaining,
        "pct": pct,
        "can_keep_going": remaining >= _KEEP_GOING_MIN_REMAINING or total > 0,
    }


def can_keep_going(user_id: int, tag: str) -> bool:
    stats = coverage_stats(user_id, tag)
    # Always allow another review chunk while universe exists; prefer when remaining > 0.
    return bool(stats.get("total", 0) > 0)


def _tables() -> list[Fact]:
    out: list[Fact] = []
    for a in range(2, 26):
        for b in range(2, 26):
            out.append(
                Fact(
                    key=f"mul:{a}x{b}",
                    prompt=f"What is ${a} \\times {b}$?",
                    answer=str(a * b),
                    speed_kind="math.tables_cell",
                )
            )
    return out


def _squares() -> list[Fact]:
    return [
        Fact(
            key=f"sq:{n}",
            prompt=f"What is ${n}^{{2}}$?",
            answer=str(n * n),
            speed_kind="math.square",
        )
        for n in range(1, 51)
    ]


def _cubes() -> list[Fact]:
    return [
        Fact(
            key=f"cu:{n}",
            prompt=f"What is ${n}^{{3}}$?",
            answer=str(n * n * n),
            speed_kind="math.cube",
        )
        for n in range(1, 31)
    ]


def _powers() -> list[Fact]:
    out: list[Fact] = []
    bases = (2, 3, 5, 7)
    for base in bases:
        max_e = {2: 12, 3: 8, 5: 6, 7: 5}[base]
        for e in range(2, max_e + 1):
            out.append(
                Fact(
                    key=f"pow:{base}^{e}",
                    prompt=f"What is ${base}^{{{e}}}$?",
                    answer=str(base**e),
                    speed_kind="math.power",
                )
            )
    return out


def _primes() -> list[Fact]:
    def is_prime(n: int) -> bool:
        if n < 2:
            return False
        if n % 2 == 0:
            return n == 2
        i = 3
        while i * i <= n:
            if n % i == 0:
                return False
            i += 2
        return True

    out: list[Fact] = []
    for n in range(2, 200):
        out.append(
            Fact(
                key=f"prime:{n}",
                prompt=f"Is ${n}$ prime? (yes/no)",
                answer="yes" if is_prime(n) else "no",
                speed_kind="math.prime_probe",
            )
        )
    return out


def _fraction_pct() -> list[Fact]:
    pairs = [
        (1, 2, 50),
        (1, 3, "33.333... or 100/3"),
        (1, 4, 25),
        (1, 5, 20),
        (1, 6, "16.666... or 50/3"),
        (1, 8, 12.5),
        (1, 10, 10),
        (1, 20, 5),
        (3, 4, 75),
        (2, 5, 40),
        (3, 5, 60),
        (4, 5, 80),
        (1, 25, 4),
        (3, 8, 37.5),
        (5, 8, 62.5),
        (7, 8, 87.5),
        (2, 3, "66.666... or 200/3"),
        (5, 6, "83.333... or 250/3"),
        (7, 10, 70),
        (9, 10, 90),
        (11, 20, 55),
        (13, 20, 65),
        (17, 20, 85),
        (19, 20, 95),
        (1, 16, 6.25),
        (3, 16, 18.75),
        (1, 12, "8.333... or 25/3"),
        (5, 12, "41.666... or 125/3"),
        (7, 12, "58.333... or 175/3"),
        (11, 12, "91.666... or 275/3"),
    ]
    out: list[Fact] = []
    for a, b, pct in pairs:
        if isinstance(pct, str):
            continue
        out.append(
            Fact(
                key=f"fp:{a}/{b}",
                prompt=f"What is $\\frac{{{a}}}{{{b}}}$ as a percent?",
                answer=str(pct).rstrip("0").rstrip(".") if isinstance(pct, float) else str(pct),
                speed_kind="math.fraction_pct",
            )
        )
        if float(pct) == int(pct):
            out.append(
                Fact(
                    key=f"pf:{int(pct)}",
                    prompt=f"What is ${int(pct)}\\%$ as a simplified fraction?",
                    answer=f"{a}/{b}",
                    speed_kind="math.pct_fraction",
                )
            )
    return out


def _shortcuts() -> list[Fact]:
    out: list[Fact] = []
    for n in range(11, 100):
        out.append(
            Fact(
                key=f"x5:{n}",
                prompt=f"Compute ${n} \\times 5$ quickly.",
                answer=str(n * 5),
                speed_kind="math.shortcut",
            )
        )
        if n % 4 == 0:
            out.append(
                Fact(
                    key=f"x25:{n}",
                    prompt=f"Compute ${n} \\times 25$ quickly.",
                    answer=str(n * 25),
                    speed_kind="math.shortcut",
                )
            )
    return out


def _units() -> list[Fact]:
    out: list[Fact] = []
    for kmh in (18, 36, 54, 72, 90, 108, 126, 144):
        out.append(
            Fact(
                key=f"kmh_ms:{kmh}",
                prompt=f"${kmh}$ km/h = how many m/s? (exact)",
                answer=str(kmh * 5 // 18),
                speed_kind="math.unit",
            )
        )
    for mins in (15, 20, 30, 45, 12, 10, 6, 5):
        from fractions import Fraction

        frac = Fraction(mins, 60)
        out.append(
            Fact(
                key=f"min_hr:{mins}",
                prompt=f"${mins}$ minutes is what fraction of an hour? (a/b)",
                answer=f"{frac.numerator}/{frac.denominator}",
                speed_kind="math.unit",
            )
        )
    return out


def _estimation() -> list[Fact]:
    out: list[Fact] = []
    samples = [
        (487, 500),
        (312, 300),
        (1540, 1500),
        (8799, 8800),
        (999, 1000),
        (2501, 2500),
        (74, 70),
        (126, 130),
    ]
    for n, nearest in samples:
        out.append(
            Fact(
                key=f"est:{n}",
                prompt=f"Estimate ${n}$ to a convenient round number for mental math (accepted: ${nearest}$).",
                answer=str(nearest),
                speed_kind="math.estimate",
            )
        )
    return out


_BUILDERS: dict[str, Callable[[], list[Fact]]] = {
    "MT0-T01": _tables,
    "MT0-T02": _primes,
    "MT0-T03": _fraction_pct,
    "MT0-T04": _squares,
    "MT0-T05": _cubes,
    "MT0-T06": _powers,
    "MT0-T07": _shortcuts,
    "MT0-T08": _units,
    "MT0-T09": _estimation,
}


def universe_for_tag(tag: str) -> list[Fact]:
    t = mc.canonical_tag(tag) or (tag or "").strip().upper()
    builder = _BUILDERS.get(t)
    if not builder:
        return []
    return list(builder())


def supports_worksheet_drills(tag: str | None) -> bool:
    t = mc.canonical_tag(tag) or (tag or "").strip().upper()
    return t in _BUILDERS


def _mul_parts(key: str) -> tuple[int, int] | None:
    if not key.startswith("mul:"):
        return None
    try:
        body = key[4:]
        a_s, b_s = body.split("x", 1)
        return int(a_s), int(b_s)
    except Exception:
        return None


def _diversify_tables(candidates: list[Fact], want: int) -> list[Fact]:
    """Spread across left/right factors so one session is not all 7×n."""
    if want <= 0 or not candidates:
        return []
    random.shuffle(candidates)
    picked: list[Fact] = []
    used_a: set[int] = set()
    used_b: set[int] = set()
    # Pass 1: prefer unused factors
    for f in candidates:
        if len(picked) >= want:
            break
        parts = _mul_parts(f.key)
        if not parts:
            picked.append(f)
            continue
        a, b = parts
        if a in used_a and b in used_b and len(picked) < want // 2:
            continue
        if a in used_a and len(used_a) < 8:
            continue
        picked.append(f)
        used_a.add(a)
        used_b.add(b)
    # Pass 2: fill
    have = {f.key for f in picked}
    for f in candidates:
        if len(picked) >= want:
            break
        if f.key not in have:
            picked.append(f)
            have.add(f.key)
    return picked[:want]


def _pick_with_coverage(
    universe: list[Fact],
    practiced: set[str],
    *,
    count: int,
    exclude_keys: set[str] | None = None,
    unpracticed_ratio: float = 0.7,
) -> list[Fact]:
    if not universe:
        return []
    exclude = exclude_keys or set()
    pool = [f for f in universe if f.key not in exclude] or list(universe)
    unprac = [f for f in pool if f.key not in practiced]
    prac = [f for f in pool if f.key in practiced]
    want = max(1, min(int(count), 40))
    n_new = int(round(want * unpracticed_ratio))
    if not unprac:
        n_new = 0
    if not prac:
        n_new = want
    n_new = min(n_new, len(unprac), want)
    n_old = min(want - n_new, len(prac))

    # Tables: diversify combinations
    if pool and pool[0].key.startswith("mul:"):
        new_pick = _diversify_tables(unprac, n_new)
        old_pick = _diversify_tables(prac, n_old)
        picked = new_pick + old_pick
    else:
        random.shuffle(unprac)
        random.shuffle(prac)
        picked = unprac[:n_new] + prac[:n_old]

    if len(picked) < want:
        rest = [f for f in pool if f not in picked]
        random.shuffle(rest)
        picked.extend(rest[: want - len(picked)])
    random.shuffle(picked)
    return picked[:want]


def _normalize_pct_answer(ans: str) -> str:
    s = str(ans).strip()
    if s.endswith("%"):
        s = s[:-1].strip()
    return s


def chunk_count() -> int:
    return int(getattr(mc, "MATH_CORE_CHUNK_COUNT", None) or mc.MATH_CORE_PRACTICE_COUNT or 12)


def generate_drill_items(
    *,
    tag: str,
    count: int | None = None,
    user_id: int | None = None,
    exclude_keys: set[str] | list[str] | None = None,
) -> list[dict[str, Any]]:
    """Build quiz-engine math items for an MT0 worksheet tag (one chunk)."""
    t = mc.canonical_tag(tag) or (tag or "").strip().upper()
    universe = universe_for_tag(t)
    if not universe:
        raise ValueError("Questions are not present for this topic.")
    want = int(count) if count is not None else chunk_count()
    practiced: set[str] = set()
    if user_id is not None:
        practiced = practiced_keys(int(user_id), t)
    excl = {str(k) for k in (exclude_keys or []) if str(k).strip()}
    facts = _pick_with_coverage(universe, practiced, count=want, exclude_keys=excl)
    items: list[dict[str, Any]] = []
    for fact in facts:
        ext = f"mcd-{t}-{fact.key}"
        items.append(
            {
                "kind": "math",
                "id": ext,
                "prompt": fact.prompt,
                "expected_answer": _normalize_pct_answer(fact.answer),
                "answer_format": "expression",
                "difficulty": "easy",
                "explanation": f"Math Core drill ({t})",
                "hint": mc.label_for_tag(t),
                "topic": t,
                "topic_id": t,
                "topic_title": mc.label_for_tag(t),
                "tags": ["math-core-drill", t, fact.speed_kind],
                "content_kind": "math",
                "note_topic_ids": [t],
                "learning_tag": t,
                "speed_fluency": True,
                "speed_kind": fact.speed_kind,
                "recall_fact": True,
                "fact_key": fact.key,
                "repeat_until_correct": True,
            }
        )
    return items
