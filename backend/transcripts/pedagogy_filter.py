"""Lecture pedagogy filter — keep technical Q&A; drop pure classroom filler."""

from __future__ import annotations

import re

# Pure session/platform filler (no conceptual teaching).
PURE_FILLER_RE = re.compile(
    r"(?i)\b("
    r"thumbs?\s*up|whatsapp|subscribe|notice\s*board|"
    r"question\s*tab|chat\s*(?:tab|functionality)|session\s*structure|"
    r"wrap[- ]?up|note[- ]taking\s*strategy|give\s*me\s*a\s*minute|"
    r"scalar\s*ui|platform\s*onboarding|settle\s*down|"
    r"hello\s*everyone|welcome\s*guys|can\s*you\s*(?:hear|see)\s*me"
    r")\b"
)

# Empty admin prompts with no nearby tech — still filler.
EMPTY_QA_RE = re.compile(
    r"(?i)^\s*(any\s+questions?|doubts?|is\s+everybody\s+clear)\s*[?.!]?\s*$"
)

# Strong API / concept tokens (one is enough to keep).
STRONG_TECH_RE = re.compile(
    r"(?i)\b("
    r"astype|dtype|ndim|ndarray|np\.|pandas|dataframe|matplotlib|"
    r"imread|imshow|reshape|newaxis|broadcast|vectoriz|"
    r"eigen|matrix|tensor|gradient|backprop|softmax|"
    r"dav|eda|numpy|rgb|grayscale"
    r")\b"
    r"|\$[^$]+\$"
    r"|`[^`]+`"
)

# Weaker tech vocabulary (need ≥2, or 1 + strong).
TECH_WORD_RE = re.compile(
    r"(?i)\b("
    r"array|arrays|tuple|shape|dimension|dimensions|index|indexing|"
    r"homogeneous|heterogeneous|mutable|immutable|overwrite|copy|"
    r"mutate|memory|contiguous|float|int|string|unicode|"
    r"library|libraries|function|method|attribute|parameter|"
    r"pixel|pixels|channel|channels|image|images|plot|visualization|"
    r"feature|features|dataset|dataframe|column|row|"
    r"algorithm|formula|equation|variable|loop|list|lists"
    r")\b"
)

_TOKEN_RE = re.compile(r"[a-z0-9_]{3,}", re.I)


def has_technical_substance(text: str) -> bool:
    """True when the span carries conceptual / API teaching content."""
    s = (text or "").strip()
    if not s:
        return False
    if STRONG_TECH_RE.search(s):
        return True
    return len(TECH_WORD_RE.findall(s)) >= 2


def is_pure_filler(text: str) -> bool:
    """True for logistics / greetings with no technical substance."""
    s = (text or "").strip()
    if not s:
        return True
    if has_technical_substance(s):
        return False
    if EMPTY_QA_RE.match(s):
        return True
    return bool(PURE_FILLER_RE.search(s))


def should_keep_transcript_span(text: str) -> bool:
    """Keep lecture spans that teach; drop pure filler."""
    s = (text or "").strip()
    if len(s) < 20:
        return False
    if is_pure_filler(s):
        return False
    return has_technical_substance(s) or len(s.split()) >= 12


def tokenize_for_overlap(text: str) -> set[str]:
    stop = {
        "the",
        "and",
        "for",
        "with",
        "that",
        "this",
        "from",
        "are",
        "was",
        "were",
        "have",
        "has",
        "will",
        "can",
        "you",
        "your",
        "our",
        "into",
        "about",
        "what",
        "when",
        "which",
        "their",
        "them",
        "then",
        "than",
        "also",
        "just",
        "like",
        "some",
        "more",
        "very",
        "been",
        "being",
        "using",
        "used",
        "use",
        "how",
        "why",
        "who",
        "not",
        "but",
        "all",
        "any",
        "out",
        "get",
        "got",
        "one",
        "two",
        "see",
        "look",
        "okay",
        "ok",
        "yes",
        "no",
    }
    return {t.lower() for t in _TOKEN_RE.findall(text or "") if t.lower() not in stop}


def hit_matches_query(
    hit: dict,
    query: str,
    *,
    min_overlap: int = 2,
) -> bool:
    """
    Keep a textbook hit only if it overlaps the lecture query.

    Blocks off-topic contamination (e.g. Image Captioning for a NumPy lecture).
    """
    q_tokens = tokenize_for_overlap(query)
    if not q_tokens:
        return False
    payload = str(hit.get("raw_payload") or "")
    citation = str(hit.get("citation") or "")
    title = str(hit.get("document_title") or hit.get("title") or "")
    breadcrumb = str(hit.get("breadcrumb") or "")
    blob = f"{citation} {title} {breadcrumb} {payload}"
    h_tokens = tokenize_for_overlap(blob)
    overlap = len(q_tokens & h_tokens)
    if overlap >= min_overlap:
        return True
    # Single strong tech token shared is enough
    strong_q = {m.group(0).lower() for m in STRONG_TECH_RE.finditer(query)}
    strong_h = {m.group(0).lower() for m in STRONG_TECH_RE.finditer(blob)}
    return bool(strong_q & strong_h)


def filter_hits_for_lecture(hits: list[dict], query: str) -> list[dict]:
    return [h for h in (hits or []) if hit_matches_query(h, query)]
