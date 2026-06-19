"""LLM tag extraction and pre-refine topic ordering.

Phase 2 of the semantic pipeline upgrade:
  1. After each CHUNK pass, ask the LLM for 1-3 hierarchical tags.
  2. Normalize near-duplicate tags with difflib fuzzy matching.
  3. Sort chunk drafts by normalized primary tag before the REFINE pass.
"""

from __future__ import annotations

import difflib
import logging
import re
from dataclasses import dataclass, field
from typing import Callable

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------
TAG_PROMPT = """Analyze these section notes. Return ONLY a TOPICS line with 1-3 hierarchical tags.
Format: TOPICS: category/subcategory, category/topic
Example: TOPICS: datascience/numpy/arrays, datascience/numpy/broadcasting
Rules:
- Use lowercase slugs separated by slashes for hierarchy.
- Return exactly one TOPICS: line, nothing else.
"""

# ---------------------------------------------------------------------------
# Regex
# ---------------------------------------------------------------------------
TOPICS_LINE_RE = re.compile(r"^TOPICS:\s*(.+)$", re.MULTILINE | re.IGNORECASE)
TAG_SEP_RE = re.compile(r"[,;]+")


@dataclass
class TaggedDraft:
    draft: str
    tags: list[str] = field(default_factory=list)
    normalized_primary: str = ""


# ---------------------------------------------------------------------------
# Tag parsing
# ---------------------------------------------------------------------------

def parse_topics_line(text: str) -> list[str]:
    """Extract tags from a TOPICS: line in LLM output."""
    m = TOPICS_LINE_RE.search(text)
    if not m:
        return []
    raw = m.group(1).strip()
    parts = TAG_SEP_RE.split(raw)
    tags: list[str] = []
    for p in parts:
        cleaned = p.strip().lower().replace(" ", "_")
        if cleaned:
            tags.append(cleaned)
    return tags


# ---------------------------------------------------------------------------
# Tag normalization (fuzzy dedup)
# ---------------------------------------------------------------------------

def _canonical_key(tag: str) -> str:
    """Sort slash-path components to normalize ordering (arrays/numpy → numpy/arrays)."""
    parts = tag.split("/")
    return "/".join(sorted(parts))


def normalize_tags(all_tags: list[list[str]], threshold: float = 0.80) -> dict[str, str]:
    """Map every raw tag to its canonical representative.

    Tags that are >threshold similar (SequenceMatcher ratio) are merged.
    The shortest / most common variant wins.

    Returns:
        mapping of raw_tag → canonical_tag
    """
    # Flatten unique
    seen: list[str] = []
    for group in all_tags:
        for t in group:
            if t not in seen:
                seen.append(t)

    mapping: dict[str, str] = {}
    clusters: list[list[str]] = []

    for tag in seen:
        placed = False
        for cluster in clusters:
            rep = cluster[0]
            ratio = difflib.SequenceMatcher(None, _canonical_key(tag), _canonical_key(rep)).ratio()
            if ratio >= threshold:
                cluster.append(tag)
                placed = True
                break
        if not placed:
            clusters.append([tag])

    for cluster in clusters:
        # Canonical = shortest tag (most general), tie-break: lexicographic
        canonical = min(cluster, key=lambda t: (len(t), t))
        for t in cluster:
            mapping[t] = canonical

    return mapping


# ---------------------------------------------------------------------------
# LLM tag extraction
# ---------------------------------------------------------------------------

def extract_tags_for_draft(
    draft: str,
    generate_fn: Callable[[str, str], str],
    opts: object,
) -> list[str]:
    """Call the LLM to extract tags for a single chunk draft.

    Args:
        draft: The CHUNK-pass output for one transcript segment.
        generate_fn: LLM generate callable: generate_fn(prompt, system) -> str
        opts: LlmOptions passed through to generate_fn.

    Returns:
        List of raw tag strings (may be empty on LLM failure).
    """
    try:
        prompt = f"{TAG_PROMPT}\n\n---\n\n{draft[:3000]}"
        response = generate_fn(prompt, opts)
        return parse_topics_line(response)
    except Exception as exc:  # noqa: BLE001
        log.warning("Tag extraction failed: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Pre-refine topic sort
# ---------------------------------------------------------------------------

def sort_drafts_by_topic(
    tagged: list[TaggedDraft],
    tag_map: dict[str, str],
) -> list[TaggedDraft]:
    """Sort chunk drafts by their normalized primary tag.

    Chunks with no tags retain their original order at the end.
    """
    def _sort_key(td: TaggedDraft) -> tuple[str, int]:
        if td.tags:
            raw = td.tags[0]
            norm = tag_map.get(raw, raw)
            return (norm, 0)
        return ("zzz_untagged", 0)

    untagged = [td for td in tagged if not td.tags]
    tagged_only = [td for td in tagged if td.tags]
    sorted_tagged = sorted(tagged_only, key=_sort_key)

    # Apply normalized_primary
    for td in sorted_tagged:
        td.normalized_primary = tag_map.get(td.tags[0], td.tags[0])

    return sorted_tagged + untagged


def annotate_draft_with_topics(td: TaggedDraft) -> str:
    """Prepend a TOPICS: annotation to a draft so REFINE can see it."""
    if not td.tags:
        return td.draft
    topics_line = "TOPICS: " + ", ".join(td.tags)
    return f"{topics_line}\n\n{td.draft}"


def strip_topics_annotations(text: str) -> str:
    """Remove all TOPICS: lines from text (called after REFINE pass)."""
    lines = text.splitlines()
    filtered = [ln for ln in lines if not TOPICS_LINE_RE.match(ln)]
    return "\n".join(filtered)
