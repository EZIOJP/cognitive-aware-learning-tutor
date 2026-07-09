"""Heuristic narrative quality scoring + optional LLM judge."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

log = logging.getLogger(__name__)

_META_PATTERNS = re.compile(
    r"(?:Confidence Score|Constraint Checklist|Plan:|Execution:|Analyze the Request)",
    re.I,
)
_TRANSITION_WORDS = re.compile(
    r"\b(?:therefore|because|however|thus|first|next|then|finally|in contrast|for example)\b",
    re.I,
)
_BULLET_LINE_RE = re.compile(r"^\s*[-*•]\s+", re.M)
_HEADING_RE = re.compile(r"^#{1,6}\s+\S", re.M)

COHERENCE_JUDGE_PROMPT = """You are a pedagogical editor. Score narrative quality of lecture notes (1-5).

5 = cohesive story, smooth transitions, preserves analogies, no bullet dumps.
3 = some paragraphs but abrupt transitions or mixed lists.
1 = dry bullet heap with no connective tissue.

Read the notes, then output JSON only: {{"score": <1-5>}}

NOTES:
{notes}
"""


@dataclass
class NarrativeAudit:
    score: int
    bullet_ratio: float
    has_meta: bool
    marker: str = ""

    @property
    def low_quality(self) -> bool:
        return self.score < 3 or self.has_meta


def narrative_quality_report(body: str) -> NarrativeAudit:
    text = (body or "").strip()
    if not text:
        return NarrativeAudit(score=1, bullet_ratio=1.0, has_meta=False, marker="NARRATIVE_LOW")

    lines = [ln for ln in text.splitlines() if ln.strip()]
    bullet_lines = sum(1 for ln in lines if _BULLET_LINE_RE.match(ln))
    bullet_ratio = bullet_lines / max(len(lines), 1)
    has_meta = bool(_META_PATTERNS.search(text[:4000]))
    headings = len(_HEADING_RE.findall(text))
    sample = text[:800]
    transitions = len(_TRANSITION_WORDS.findall(sample))

    score = 4
    if bullet_ratio > 0.6:
        score -= 2
    elif bullet_ratio > 0.4:
        score -= 1
    if headings == 0:
        score -= 1
    if transitions == 0 and len(text) > 500:
        score -= 1
    if has_meta:
        score -= 2
    score = max(1, min(5, score))

    marker = ""
    if score < 3 or has_meta:
        marker = "NARRATIVE_LOW"

    return NarrativeAudit(
        score=score,
        bullet_ratio=round(bullet_ratio, 3),
        has_meta=has_meta,
        marker=marker,
    )


def apply_narrative_marker(body: str, audit: NarrativeAudit) -> str:
    if not audit.marker or audit.marker in body:
        return body
    return f"<!-- {audit.marker}: heuristic score {audit.score}/5 -->\n\n{body}"


def llm_narrative_judge(
    body: str,
    *,
    generate_fn,
    max_chars: int = 12_000,
) -> int | None:
    """Optional G-Eval style judge; returns 1-5 or None on failure."""
    prompt = COHERENCE_JUDGE_PROMPT.format(notes=body[:max_chars])
    try:
        raw = generate_fn(prompt)
    except Exception as exc:  # noqa: BLE001
        log.warning("Narrative judge failed: %s", exc)
        return None
    if not raw:
        return None
    match = re.search(r"\{\s*\"score\"\s*:\s*(\d)\s*\}", raw)
    if match:
        return int(match.group(1))
    try:
        data = json.loads(raw.strip())
        score = int(data.get("score", 0))
        return score if 1 <= score <= 5 else None
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
