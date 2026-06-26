"""LLM tag extraction and pre-refine topic ordering."""

from __future__ import annotations

import difflib
import logging
import re
from dataclasses import dataclass, field
from typing import Callable

log = logging.getLogger(__name__)

TAG_PROMPT = """Analyze these section notes. Return ONLY a TOPICS line with 1-3 hierarchical tags.
Format: TOPICS: category/subcategory, category/topic
Example: TOPICS: python/basics/loops, python/numpy/arrays
Rules:
- Use lowercase slugs separated by slashes for hierarchy.
- Align tags to source file topics when mentioned in the notes.
- Return exactly one TOPICS: line, nothing else.
"""

TOPICS_LINE_RE = re.compile(r"^TOPICS:\s*(.+)$", re.MULTILINE | re.IGNORECASE)
TAG_SEP_RE = re.compile(r"[,;]+")


@dataclass
class TaggedDraft:
    draft: str
    tags: list[str] = field(default_factory=list)
    normalized_primary: str = ""


def parse_topics_line(text: str) -> list[str]:
    m = TOPICS_LINE_RE.search(text)
    if not m:
        return []
    parts = TAG_SEP_RE.split(m.group(1).strip())
    return [p.strip().lower().replace(" ", "_") for p in parts if p.strip()]


def _canonical_key(tag: str) -> str:
    return "/".join(sorted(tag.split("/")))


def normalize_tags(all_tags: list[list[str]], threshold: float = 0.80) -> dict[str, str]:
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
            ratio = difflib.SequenceMatcher(None, _canonical_key(tag), _canonical_key(cluster[0])).ratio()
            if ratio >= threshold:
                cluster.append(tag)
                placed = True
                break
        if not placed:
            clusters.append([tag])

    for cluster in clusters:
        canonical = min(cluster, key=lambda t: (len(t), t))
        for t in cluster:
            mapping[t] = canonical
    return mapping


def extract_tags_for_draft(
    draft: str,
    generate_fn: Callable[[str, object], str | None],
    opts: object,
) -> list[str]:
    try:
        prompt = f"{TAG_PROMPT}\n\n---\n\n{draft[:3000]}"
        response = generate_fn(prompt, opts)
        if not response:
            return []
        return parse_topics_line(response)
    except Exception as exc:  # noqa: BLE001
        log.warning("Tag extraction failed: %s", exc)
        return []


def sort_drafts_by_topic(tagged: list[TaggedDraft], tag_map: dict[str, str]) -> list[TaggedDraft]:
    def _sort_key(td: TaggedDraft) -> tuple[str, int]:
        if td.tags:
            return (tag_map.get(td.tags[0], td.tags[0]), 0)
        return ("zzz_untagged", 0)

    untagged = [td for td in tagged if not td.tags]
    sorted_tagged = sorted([td for td in tagged if td.tags], key=_sort_key)
    for td in sorted_tagged:
        td.normalized_primary = tag_map.get(td.tags[0], td.tags[0])
    return sorted_tagged + untagged


def annotate_draft_with_topics(td: TaggedDraft) -> str:
    if not td.tags:
        return td.draft
    return f"TOPICS: {', '.join(td.tags)}\n\n{td.draft}"


def strip_topics_annotations(text: str) -> str:
    return "\n".join(ln for ln in text.splitlines() if not TOPICS_LINE_RE.match(ln))
