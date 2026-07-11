"""Post-merge enrichment — add mermaid diagrams and code blocks after full notes exist.

Chunk generation is text-only; this is the single place visuals are added.
Long documents are enriched in section batches so nothing is truncated,
and a shrink guard keeps the original text if the model drops content.
"""

from __future__ import annotations

import logging
import re
from typing import Callable

from backend.core.ollama_client import LlmOptions, ollama_available, ollama_generate
from backend.transcripts.cleanup import postprocess_markdown
from backend.transcripts.mermaid.prompts import MERMAID_GENERATION_RULES
from backend.transcripts.notes_generator import _escape_format_braces

log = logging.getLogger(__name__)


def _embed_rules(rules: str) -> str:
    """Escape braces so embedded rules survive the later .format(body=...) call."""
    return _escape_format_braces(rules.strip())

GenerateFn = Callable[[str], str | None]

ENRICH_PROMPT = f"""You are enhancing CONCEPTUAL revision notes with visual aids.

Rules:
- Keep ALL existing topic headings, concept bullets, and prose — do not shorten or rewrite the notes.
- Do not reintroduce classroom/speaker chatter.
- Add at most ONE ```mermaid diagram per major ## section, only when a flow, process, or relationship is described.
- Add ```python (or relevant language) code blocks only where algorithms or code are clearly discussed in the text.
- Do NOT add mermaid to every section — skip sections that are definitions or lists only.
{_embed_rules(MERMAID_GENERATION_RULES)}
- Output the COMPLETE markdown document only (no preamble, no reasoning, no planning).
- Never replace the notes with diagram-only output — embed diagrams inside the existing sections.

Notes:
{{body}}
"""

_META_ENRICH_RE = re.compile(
    r"(?:Analyze the Request|Rules Check|Plan Execution|Output ONLY the diagram|"
    r"The user wants me to enhance)",
    re.I,
)
_HEADING_RE = re.compile(r"(?m)^#{1,6}\s+\S")

# Batches for long documents; keeps each LLM call well inside local-model context.
_BATCH_CHAR_LIMIT = 24_000
# If the model returns much less text than it was given, assume it dropped content.
_SHRINK_GUARD_RATIO = 0.6

_SECTION_SPLIT_RE = re.compile(r"^(?=## )", re.MULTILINE)


def _split_section_batches(text: str, *, max_chars: int) -> list[str]:
    """Split on ## headings and regroup into batches under max_chars each."""
    parts = [p for p in _SECTION_SPLIT_RE.split(text) if p.strip()]
    if not parts:
        return [text]

    batches: list[str] = []
    current: list[str] = []
    current_len = 0
    for part in parts:
        if current and current_len + len(part) > max_chars:
            batches.append("".join(current))
            current = []
            current_len = 0
        current.append(part)
        current_len += len(part)
    if current:
        batches.append("".join(current))
    return batches


def _heading_count(text: str) -> int:
    return len(_HEADING_RE.findall(text))


def _enrich_batch(
    batch: str,
    *,
    llm: LlmOptions | None,
    generate_fn: GenerateFn | None,
) -> str:
    """Enrich one batch; return the original text when output is empty or shrunk."""
    prompt = ENRICH_PROMPT.format(body=_escape_format_braces(batch))
    if generate_fn is not None:
        enriched = generate_fn(prompt)
    else:
        enriched = ollama_generate(prompt, timeout=240.0, llm=llm, task="note_enrich")

    if not enriched or not enriched.strip():
        return batch
    enriched = postprocess_markdown(enriched.strip(), sanitize_mermaid=False)
    batch_stripped = batch.strip()
    if _META_ENRICH_RE.search(enriched) and _heading_count(enriched) < _heading_count(batch_stripped):
        log.warning("Visual enrich returned reasoning text — keeping original batch")
        return batch
    src_headings = _heading_count(batch_stripped)
    out_headings = _heading_count(enriched)
    if src_headings > 0 and out_headings < max(1, src_headings - 1):
        log.warning(
            "Visual enrich dropped section headings (%d -> %d) — keeping original batch",
            src_headings,
            out_headings,
        )
        return batch
    if len(enriched) < len(batch_stripped) * _SHRINK_GUARD_RATIO:
        log.warning(
            "Visual enrich shrank a batch (%d -> %d chars) — keeping original text",
            len(batch),
            len(enriched),
        )
        return batch
    return enriched


def enrich_note_with_visuals(
    body: str,
    *,
    llm: LlmOptions | None = None,
    generate_fn: GenerateFn | None = None,
    on_progress: Callable[[str], None] | None = None,
    max_chars: int = _BATCH_CHAR_LIMIT,
) -> str:
    """Final-phase pass to insert mermaid + code into the merged, text-only document."""
    text = (body or "").strip()
    if not text:
        return text
    if generate_fn is None and not ollama_available(llm):
        if on_progress:
            on_progress("Visual enrich skipped — LLM offline")
        return text

    batches = _split_section_batches(text, max_chars=max_chars)
    total = len(batches)
    if on_progress:
        if total == 1:
            on_progress("Enriching notes — adding diagrams and code blocks…")
        else:
            on_progress(f"Enriching notes in {total} section batches — adding diagrams and code blocks…")

    enriched_parts: list[str] = []
    for i, batch in enumerate(batches, start=1):
        if total > 1 and on_progress:
            on_progress(f"Enrich batch {i}/{total}…")
        # Oversized single sections are passed through untouched rather than truncated.
        if len(batch) > max_chars * 1.5:
            enriched_parts.append(batch.strip())
            continue
        enriched_parts.append(_enrich_batch(batch, llm=llm, generate_fn=generate_fn))

    result = "\n\n".join(p.strip() for p in enriched_parts if p.strip())
    if not result:
        log.warning("Visual enrich returned empty — keeping text-only notes")
        if on_progress:
            on_progress("Visual enrich returned empty — saved text-only notes")
        return text

    if on_progress:
        on_progress("Visual enrich complete")
    return result
