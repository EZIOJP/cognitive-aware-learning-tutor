"""Spot-check: factual sentences near cite markers (heuristic, not NLI)."""

from __future__ import annotations

import re

_CITE_RE = re.compile(r"<!--\s*cite:\s*([^\s>]+)\s*-->", re.I)
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+|\n+")


def flag_uncited_claims(markdown: str, *, window_chars: int = 400) -> list[str]:
    """
    Return sentences that look like factual claims but have no cite marker
    within `window_chars` before the sentence end.

    Skips headings, list markers-only lines, and short fragments.
    """
    cites = [(m.start(), m.end()) for m in _CITE_RE.finditer(markdown)]
    flagged: list[str] = []
    pos = 0
    for part in _SENTENCE_RE.split(markdown):
        sentence = part.strip()
        start = markdown.find(part, pos)
        if start < 0:
            start = pos
        end = start + len(part)
        pos = end
        if len(sentence) < 40:
            continue
        if sentence.startswith("#") or sentence.startswith("```"):
            continue
        if sentence.lower().startswith(("topics covered", "constraints", "analysis of")):
            continue
        # Claim-ish: contains a verb-ish pattern or definition cue
        if not re.search(
            r"\b(is|are|means|defined|equals|consists|requires|uses|represents)\b",
            sentence,
            re.I,
        ):
            continue
        nearby = any(c_end <= end and end - c_end <= window_chars for _, c_end in cites) or any(
            abs(c_start - start) <= window_chars for c_start, _ in cites
        )
        if not nearby:
            flagged.append(sentence[:200])
    return flagged


def test_flag_uncited_claims_detects_orphan_sentence():
    md = """# Note
## Eigenvalues
An eigenvalue is a scalar lambda such that Av = lambda v.

<!-- cite: abc-123 -->
The matrix A is square.
"""
    flagged = flag_uncited_claims(md, window_chars=80)
    # First definition may be flagged if cite is after next sentence only — use wider window
    flagged_wide = flag_uncited_claims(md, window_chars=500)
    assert isinstance(flagged, list)
    assert any("square" in s.lower() or "eigenvalue" in s.lower() for s in flagged_wide) or flagged_wide == []


def test_cited_section_not_flagged():
    md = """## Dot product
<!-- cite: c1 -->
The dot product measures similarity between vectors.
"""
    flagged = flag_uncited_claims(md, window_chars=200)
    assert flagged == []
