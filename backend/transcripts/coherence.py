"""Cross-chunk coherence modes: compact (default), sequential, cloud_heavy."""

from __future__ import annotations

import logging
import re
from typing import Callable

log = logging.getLogger(__name__)

GLOSSARY_MARKER = "### Semantic Glossary"
SEQUENTIAL_CHAR_LIMIT = 20_000

GenerateFn = Callable[[str], str | None]

NARRATIVE_RULES = """ROLE: Expert tutor writing CONCEPTUAL revision notes grounded in textbook/corpus reference.

PURPOSE:
- Notes BRIEF the lecture's topics so a student can revise the whole arc — not a diary of the speaker or classroom.
- REFERENCE (RAG / textbook chunks) is the conceptual authority: fill definitions, properties, steps, formulas from the book.
- TRANSCRIPT only signals which topics were covered, in what order, and class-specific examples/emphasis.

FACTUAL-LOCK:
- Prefer reference for definitions, properties, and standard steps. Do not invent theories.
- Do not assert any factual claim that is not supported by REFERENCE (or an explicit cite). Transcript is topic signal only.
- Preserve technical terms exactly. Do not substitute synonyms.
- If a step is incomplete, mark it briefly — do not invent fixes.

DROP (never write these):
- Classroom / platform logistics: thumbs up, pace, WhatsApp, subscribe, "any questions", doubt-session admin.
- Platform UI: notice board, chat tab, question tab, Scalar/LMS onboarding, session structure, wrap-up, note-taking strategy tips.
- Speaker narration: "he said", "look at this slide", "give me a minute".
- LLM meta: confidence scores, constraints checklists, self-correction asides.
- Fixed encyclopedia templates: do not structure every section as Definition / Importance / Key Components / Conclusion.

STYLE:
- ## / ### headings = concept names in lecture order.
- Under each: a short conceptual BRIEF (1–3 short paragraphs or tight bullets) that explains the idea using REFERENCE meat.
- Define new concepts before using them later. Use $LaTeX$ for equations when needed.
- Text only: no mermaid or ``` code blocks in this pass.
- Output markdown ONLY — no preamble, planning, or meta commentary."""

NARRATIVE_FIRST_CHUNK_SUFFIX = """
After the notes, add a short section:
### Semantic Glossary
List key terms and formulas introduced (one line each, max 12 items) — revision checklist.
On the FIRST chunk only, you may also start with ## Topics covered (bullets) as a revision map."""

COMPACT_CONTEXT = """
ACTIVE SEMANTIC GLOSSARY (do not repeat these definitions):
{glossary}

PREVIOUS CONCEPT/TOPIC: {prior_heading}
Continue with the next concept; do not re-explain prior definitions or classroom/platform chatter."""

SEQUENTIAL_REFINE = """
You are refining continuous CONCEPTUAL revision notes (textbook/corpus grounded).

ACTIVE SEMANTIC MEMORY:
{glossary}

EXISTING NOTES:
{running_notes}

NEW LECTURE SEGMENT:
{chunk}

TASK: Integrate new TOPICS/CONCEPTS into the existing notes as readable topic briefs (not Definition/Importance templates). Prefer reference-backed facts. Drop classroom/platform filler. Avoid duplicate definitions. Update ### Semantic Glossary. Output the full merged document plus glossary at the end."""


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
