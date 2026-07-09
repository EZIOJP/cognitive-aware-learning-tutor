"""Cross-chunk coherence modes: compact (default), sequential, cloud_heavy."""

from __future__ import annotations

import logging
import re
from typing import Callable

log = logging.getLogger(__name__)

GLOSSARY_MARKER = "### Semantic Glossary"
SEQUENTIAL_CHAR_LIMIT = 20_000

GenerateFn = Callable[[str], str | None]

NARRATIVE_RULES = """ROLE: Expert academic scribe translating spoken lectures into flowing narrative notes.

FACTUAL-LOCK:
- Use ONLY facts from the transcript and reference material. Do not invent examples or theories.
- Preserve technical terms exactly. Do not substitute synonyms.
- If a step is incomplete in the source, note it as spoken — do not guess fixes.

STYLE:
- Write cohesive paragraphs (not dry bullet dumps). Preserve analogies and step-by-step explanations.
- Define new concepts before using them in later sentences.
- Use ## or ### headings for topic shifts. Use $LaTeX$ for equations when needed.
- Text only: no mermaid or ``` code blocks in this pass.
- Output markdown ONLY — no preamble, planning, confidence scores, or meta commentary."""

NARRATIVE_FIRST_CHUNK_SUFFIX = """
After the notes, add a short section:
### Semantic Glossary
List key terms and formulas introduced (one line each, max 12 items)."""

COMPACT_CONTEXT = """
ACTIVE SEMANTIC GLOSSARY (do not repeat these definitions):
{glossary}

PREVIOUS SECTION TOPIC: {prior_heading}
Continue chronologically without repeating prior definitions."""

SEQUENTIAL_REFINE = """
You are refining continuous lecture notes.

ACTIVE SEMANTIC MEMORY:
{glossary}

EXISTING NARRATIVE NOTES:
{running_notes}

NEW LECTURE SEGMENT:
{chunk}

TASK: Integrate the new segment into the existing notes. Maintain chronological flow, avoid duplicate definitions, update the Semantic Glossary with new terms. Output the full merged document plus ### Semantic Glossary at the end."""


def resolve_coherence_mode(mode: str | None, *, llm_tier: str | None = None) -> str:
    """Resolve coherence mode; cloud_heavy when tier is heavy/cloud."""
    key = (mode or "compact").strip().lower()
    if key == "auto":
        if llm_tier and llm_tier.strip().lower() in ("heavy", "cloud", "premium"):
            return "cloud_heavy"
        return "compact"
    if key == "cloud_heavy":
        if llm_tier and llm_tier.strip().lower() in ("heavy", "cloud", "premium"):
            return "cloud_heavy"
        log.info("cloud_heavy requested but no heavy tier — using sequential")
        return "sequential"
    if key in ("sequential", "compact"):
        return key
    return "compact"


def parse_semantic_response(text: str) -> tuple[str, str]:
    """Split narrative notes from optional Semantic Glossary block."""
    raw = (text or "").strip()
    if not raw:
        return "", ""
    if GLOSSARY_MARKER in raw:
        parts = raw.split(GLOSSARY_MARKER, 1)
        notes = parts[0].strip()
        glossary = (GLOSSARY_MARKER + parts[1]).strip()[:600]
        return notes, glossary
    return raw, ""


def extract_heading(section: str) -> str:
    for line in section.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return re.sub(r"^#+\s*", "", stripped).strip()[:120]
    return ""


def extract_glossary_from_section(section: str) -> str:
    _, glossary = parse_semantic_response(section)
    return glossary


def merge_glossary(existing: str, new: str) -> str:
    if not new.strip():
        return existing
    if not existing.strip():
        return new.strip()[:600]
    combined = f"{existing.strip()}\n{new.strip()}"
    return combined[:600]


def build_narrative_chunk_prompt(
    *,
    chunk: str,
    reference: str,
    is_first: bool,
    glossary: str = "",
    prior_heading: str = "",
) -> str:
    parts = [NARRATIVE_RULES]
    if reference.strip() and reference.strip() != "(none)":
        parts.append(f"\nReference material:\n{reference.strip()[:6000]}")
    if not is_first and (glossary.strip() or prior_heading.strip()):
        parts.append(
            COMPACT_CONTEXT.format(
                glossary=glossary.strip() or "(none yet)",
                prior_heading=prior_heading.strip() or "(start of lecture)",
            )
        )
    if is_first:
        parts.append(NARRATIVE_FIRST_CHUNK_SUFFIX)
    parts.append(f"\nTranscript chunk:\n{chunk}")
    return "\n".join(parts)


def build_sequential_prompt(
    *,
    chunk: str,
    reference: str,
    running_notes: str,
    glossary: str,
    is_first: bool,
) -> str:
    if is_first:
        return build_narrative_chunk_prompt(
            chunk=chunk,
            reference=reference,
            is_first=True,
        )
    return (
        NARRATIVE_RULES
        + "\n"
        + SEQUENTIAL_REFINE.format(
            glossary=glossary.strip() or "(none)",
            running_notes=running_notes[:18_000],
            chunk=chunk[:12_000],
        )
    )


def coherence_task(mode: str) -> str:
    return "notes_coherence" if mode == "cloud_heavy" else "notes_chunk"
