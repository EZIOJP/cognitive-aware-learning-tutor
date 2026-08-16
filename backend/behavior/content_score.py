"""Weighted page-text distraction score (on-device; mirrored in gate_policy.js)."""
from __future__ import annotations

import re
from typing import Literal

Action = Literal["continue", "stop", "warn", "lock"]

# Prefer phrases; weights 1–5. Keep in sync with calt-gate-extension/gate_policy.js.
CONTENT_SCORE_WEIGHTS: dict[str, int] = {
    "pornography": 4,
    "hardcore porn": 5,
    "porn": 4,
    "porno": 4,
    "xxx video": 5,
    "xxx": 3,
    "nsfw": 2,
    "hentai": 4,
    "onlyfans": 4,
    "fansly": 3,
    "chaturbate": 4,
    "blowjob": 5,
    "handjob": 5,
    "cumshot": 5,
    "creampie": 5,
    "gangbang": 5,
    "threesome": 4,
    "deepthroat": 5,
    "bdsm": 3,
    "bondage": 3,
    "fetish": 2,
    "pegging": 4,
    "milf": 3,
    "incest": 5,
    "rule34": 4,
    "rule 34": 4,
    "nude pics": 4,
    "nude photo": 4,
    "nudes": 3,
    "nudity": 2,
    "nude": 2,
    "naked pics": 4,
    "naked photo": 4,
    "erotic": 2,
    "erotica": 2,
    "live sex": 5,
    "sex cam": 5,
    "sex tape": 5,
    "sex video": 4,
    "adult video": 3,
    "camgirl": 4,
    "cam girl": 4,
    "erome": 4,
    "eporner": 4,
    "redgifs": 4,
    "pornhub": 4,
    "xvideos": 4,
    "xhamster": 4,
}

THRESHOLDS_FREE = {"warn": 8, "lock": 16, "max_samples": 5}
THRESHOLDS_STUDY = {"warn": 5, "lock": 10, "max_samples": 3}


def _thresholds(mode: str) -> dict[str, int]:
    return THRESHOLDS_STUDY if (mode or "").strip().lower() == "study" else THRESHOLDS_FREE


def score_haystack(
    text: str,
    weights: dict[str, int] | None = None,
    per_term_cap: int = 3,
) -> tuple[int, list[str]]:
    hay = (text or "").lower()
    wmap = weights if weights is not None else CONTENT_SCORE_WEIGHTS
    # Longer phrases first so "hardcore porn" wins over "porn"
    terms = sorted(wmap.keys(), key=len, reverse=True)
    score = 0
    matched: list[str] = []
    for term in terms:
        weight = int(wmap[term])
        if weight <= 0 or len(term) < 3:
            continue
        escaped = re.escape(term)
        pat = re.compile(rf"(^|[^a-z0-9]){escaped}([^a-z0-9]|$)", re.I)
        hits = len(pat.findall(hay))
        if hits <= 0:
            continue
        use = min(hits, per_term_cap)
        score += weight * use
        matched.append(term)
        # Prevent shorter overlapping recount on same span: scrub matched phrase
        hay = pat.sub(r"\1 \2", hay)
    return score, matched


def decide_content_action(
    *,
    score: int,
    prev_score: int,
    sample_index: int,
    warned: bool,
    mode: str,
) -> Action:
    th = _thresholds(mode)
    warn_at = th["warn"]
    lock_at = th["lock"]
    max_samples = th["max_samples"]

    if score >= lock_at:
        return "lock"
    if score >= warn_at:
        if warned and score > prev_score:
            return "lock"
        if not warned:
            return "warn"
        # warned but flat — keep sampling until max, then stop
    if sample_index >= 1 and score < warn_at and abs(score - prev_score) <= 1:
        return "stop"
    if sample_index + 1 >= max_samples:
        return "stop"
    return "continue"
