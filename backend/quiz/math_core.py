"""Math Core — daily fluency block (tables / divisibility / powers).

Always first in today’s Study Loop freeze when practice inventory exists.
Must: read + MATH_CORE_PRACTICE_COUNT questions. Extra free practice is encouraged.

Worksheet IDs use **MT0-Txx** (basics-first). Legacy MT1-T16…T24 still resolve.
"""

from __future__ import annotations

# Primary tag for generators + bank (MT1 number systems).
MATH_CORE_TAG = "MT1-T01"
MATH_CORE_LABEL = "Math Core"
# Minimum gated questions for MT1 Math Core warm-up (daily bite).
MATH_CORE_PRACTICE_COUNT = 20
# First chunk size for MT0 fluency drills (Keep going appends more).
MATH_CORE_CHUNK_COUNT = 12

# Basics-first worksheet order (MT0 = fluency foundation before interview MT1-T02+).
# Pedagogical sequence: tables → primes → fractions → squares → cubes → powers →
# shortcuts → units → estimation.
MATH_CORE_WORKSHEETS: tuple[tuple[str, str], ...] = (
    ("MT0-T01", "tables 2–25"),
    ("MT0-T02", "primes & factorization"),
    ("MT0-T03", "fraction ↔ %"),
    ("MT0-T04", "squares"),
    ("MT0-T05", "cubes"),
    ("MT0-T06", "powers"),
    ("MT0-T07", "calculation shortcuts"),
    ("MT0-T08", "unit conversions"),
    ("MT0-T09", "approximation & estimation"),
)

# Legacy worksheet IDs → canonical MT0 (notes / SRS / stub flags may still use old ids).
LEGACY_WORKSHEET_ALIASES: dict[str, str] = {
    "MT1-T19": "MT0-T01",
    "MT1-T21": "MT0-T02",
    "MT1-T20": "MT0-T03",
    "MT1-T16": "MT0-T04",
    "MT1-T17": "MT0-T05",
    "MT1-T18": "MT0-T06",
    "MT1-T22": "MT0-T07",
    "MT1-T23": "MT0-T08",
    "MT1-T24": "MT0-T09",
}

# Companion read topics — warm-up + worksheets in learn order.
MATH_CORE_READ_TAGS: tuple[str, ...] = (
    MATH_CORE_TAG,
    *(tid for tid, _ in MATH_CORE_WORKSHEETS),
)

_WORKSHEET_LABELS: dict[str, str] = {
    tid: f"{MATH_CORE_LABEL} · {title}" for tid, title in MATH_CORE_WORKSHEETS
}

# Stable sort key for Learn tree (lower = earlier).
_LEARN_ORDER: dict[str, int] = {
    MATH_CORE_TAG: 0,
    **{tid: i + 1 for i, (tid, _) in enumerate(MATH_CORE_WORKSHEETS)},
}
for legacy, canon in LEGACY_WORKSHEET_ALIASES.items():
    _LEARN_ORDER[legacy] = _LEARN_ORDER[canon]


def canonical_tag(tag: str | None) -> str:
    """Map legacy MT1-T16…T24 → MT0-Txx; otherwise normalize case."""
    t = (tag or "").strip().upper()
    if not t:
        return ""
    return LEGACY_WORKSHEET_ALIASES.get(t, t)


def learn_order(tag: str | None) -> int:
    """Display / queue rank within Math Core (basics first)."""
    t = canonical_tag(tag)
    if t in _LEARN_ORDER:
        return _LEARN_ORDER[t]
    # Other MT1 interview topics after fluency block
    if t.startswith("MT1-"):
        return 100
    if t.startswith("MT0-"):
        return 50
    return 999


def is_math_core_tag(tag: str | None) -> bool:
    return canonical_tag(tag) == MATH_CORE_TAG


def is_math_core_read_tag(tag: str | None) -> bool:
    t = canonical_tag(tag)
    return t in {x.upper() for x in MATH_CORE_READ_TAGS} or t in LEGACY_WORKSHEET_ALIASES


def is_math_core_folder_tag(tag: str | None) -> bool:
    t = canonical_tag(tag)
    if not t:
        return False
    if t in {x.upper() for x in MATH_CORE_READ_TAGS}:
        return True
    if t.startswith("MT0-") or t.startswith("MT1-"):
        return True
    return t in LEGACY_WORKSHEET_ALIASES


def practice_count_for_tag(tag: str, *, default: int = 15) -> int:
    t = canonical_tag(tag) or (tag or "").strip().upper()
    # MT0 worksheets: short chunk; Keep going extends.
    if t.startswith("MT0-T") or t in LEGACY_WORKSHEET_ALIASES:
        return MATH_CORE_CHUNK_COUNT
    if is_math_core_tag(t):
        return MATH_CORE_PRACTICE_COUNT
    return default


def practice_tag_for(tag: str | None) -> str:
    """Identity for worksheets (own drills). Warm-up / empty → MT1-T01."""
    raw = (tag or "").strip()
    if not raw:
        return MATH_CORE_TAG
    # Worksheets keep their own tag (drills). Only bare aliases stay as-is.
    return canonical_tag(raw) or raw


def label_for_tag(tag: str | None) -> str:
    t = canonical_tag(tag)
    if t == MATH_CORE_TAG:
        return MATH_CORE_LABEL
    if t in _WORKSHEET_LABELS:
        return _WORKSHEET_LABELS[t]
    return (tag or "").strip() or "topic"
