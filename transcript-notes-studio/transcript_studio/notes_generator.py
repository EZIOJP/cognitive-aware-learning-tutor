"""Generate markdown lecture notes from cleaned transcripts via local LLM."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from transcript_studio.cleanup import (
    chunk_by_words,
    clean_transcript,
    count_code_blocks,
    count_mermaid_blocks,
    postprocess_markdown,
)
from transcript_studio.semantic_chunker import semantic_chunk as _semantic_chunk
from transcript_studio.tag_engine import (
    TaggedDraft,
    annotate_draft_with_topics,
    extract_tags_for_draft,
    normalize_tags,
    sort_drafts_by_topic,
    strip_topics_annotations,
)
from transcript_studio.wikilink_injector import inject_wikilinks as _inject_wikilinks
from transcript_studio.config import AppConfig, load_config
from transcript_studio.context_loader import load_context_folder
from transcript_studio.llm_client import LlmOptions, generate, llm_available, options_from_config
from transcript_studio.snapshots import SNAPSHOT_MARKER_RE, inject_snapshot_images
from transcript_studio.source_loader import (
    combine_source_files,
    list_source_files,
    load_source_file,
    prepare_sources,
    reference_slice,
)

log = logging.getLogger(__name__)

CHUNK_PROMPT = """You are creating comprehensive lecture study notes from one section of a class recording.

Rules:
- Output markdown ONLY (no preamble).
- Use ## and ### headings for every distinct topic taught in this section.
- Be thorough: cover ALL concepts, definitions, examples, and instructor explanations in this chunk — do not summarize to only 3 bullets.
- Use bullet lists, short paragraphs, and tables where helpful.
- Match topic headings to reference file names when a reference covers that topic (e.g. ### NumPy arrays from Lecture_1__Introduction_to_Numpy).
- Preserve markdown concepts as prose above any code — explain the idea before showing syntax.
- Use ```python fences ONLY for Python; syntax must be valid and runnable.
- Provide exactly one short explanation paragraph immediately before each code block.
- Copy or adapt code from the reference materials below — do not invent APIs, functions, or libraries not in the transcript or references.
- If a process or workflow is described, include a ```mermaid flowchart.
- Keep [SNAPSHOT N] markers on their own lines where they appear.
- Do not skip topics because they seem basic.

Reference materials for this section (Colab notebooks, slide PDFs, prereqs — weave relevant code/examples in):
{reference}

Lecture transcript section:
{chunk}
"""

REFINE_PROMPT = """You are merging section notes into one cohesive, COMPLETE study guide for the full lecture.

Tasks:
- Merge duplicate ## sections; keep ALL unique topics — do not shorten or omit content
- Output length must stay at or above the draft length — do NOT compress or summarize away detail
- Reorder for logical flow (intro → core concepts → examples → labs → summary)
- Within each major topic, use this section order: Concept → Why it matters → Example → Snippet → Pitfalls
- Deduplicate intro roll-call, attendance, and chit-chat from live captions — keep only teaching content
- Repair broken ```mermaid and ``` code fences
- Keep [SNAPSHOT N] markers on their own lines
- Weave in Colab/notebook code from references under ### Examples or ### Colab lab sections near matching topics
- Add missing topics that appear in references but were skipped in the draft
- End with ## Key takeaways (6-10 bullets covering the full class)
- TOPICS: annotation lines are semantic grouping hints — use them to merge and reorder sections logically
- Remove ALL TOPICS: lines from final output

Supplementary references (PDFs, Colab exports, prereqs):
{context}

Draft notes to merge (keep depth — do not compress):
{draft}
"""

ENRICH_PROMPT = """Enhance these lecture notes using the reference materials. The notes must become MORE complete, not shorter.

For each major topic, add where relevant:
- Under code examples use this order: Explanation → Code → Expected output / note
- ### Colab / code examples — short runnable snippets (max 15–25 lines per snippet)
- ### Instructor emphasis — practical tips mentioned in slides
- Compare & contrast tables when references have competing concepts (e.g. list vs ndarray, EDA steps)

PDF / Colab reference clean-up:
- Strip execution markers (In [1]:, Out [2]:, etc.) from reference text
- Format code into clean ```python or ```text fenced blocks without markers
- If a code block appears truncated due to PDF pagination, logically complete the syntax based on context

Keep all existing sections. Only ADD and refine; never delete topics.

References:
{context}

Current notes:
{notes}
"""


def strip_snapshot_markers(raw: str) -> str:
    return SNAPSHOT_MARKER_RE.sub(lambda m: f"\n*[Slide {m.group(1)}]*\n", raw)


def parse_transcript(raw: str, *, aggressive: bool = False, preserve_snapshots: bool = False) -> str:
    if not preserve_snapshots:
        raw = strip_snapshot_markers(raw)
    return clean_transcript(raw, aggressive=aggressive)


def _split_h2_sections(markdown: str) -> list[str]:
    parts = re.split(r"(?=^## )", markdown.strip(), flags=re.MULTILINE)
    return [p.strip() for p in parts if p.strip()]


def summarize_chunk(
    chunk: str,
    *,
    aggressive: bool = False,
    reference_hint: str = "",
    opts: LlmOptions | None = None,
) -> str | None:
    prompt = CHUNK_PROMPT.format(
        chunk=chunk[:16000],
        reference=reference_hint[:8000] if reference_hint else "(none)",
    )
    if aggressive:
        prompt = (
            "This section comes from noisy Windows Live Captions (repeated growing lines). "
            "Extract the actual lecture content only; ignore duplicate partial phrases.\n\n" + prompt
        )
    return generate(prompt, opts=opts, timeout=240.0)


def _refine_once(draft: str, *, title: str, context: str, opts: LlmOptions) -> str | None:
    prompt = REFINE_PROMPT.format(
        context=context[:40000] if context else "(none)",
        draft=draft[:50000],
    )
    prompt = f"Title for the document: {title}\n\n" + prompt
    return generate(prompt, opts=opts, timeout=300.0)


def refine_notes(
    draft: str,
    *,
    title: str,
    context: str,
    opts: LlmOptions | None = None,
) -> str | None:
    llm_opts = opts or options_from_config()
    if len(draft) <= 45000:
        return _refine_once(draft, title=title, context=context, opts=llm_opts)

    sections = _split_h2_sections(draft)
    if len(sections) <= 1:
        return _refine_once(draft, title=title, context=context, opts=llm_opts)

    refined_parts: list[str] = []
    batch_size = 3
    for i in range(0, len(sections), batch_size):
        batch = "\n\n".join(sections[i : i + batch_size])
        part = _refine_once(batch, title=title, context=context, opts=llm_opts)
        if part:
            refined_parts.append(postprocess_markdown(part))

    if not refined_parts:
        return None

    combined = "\n\n".join(refined_parts)
    if len(combined) <= 45000:
        return _refine_once(combined, title=title, context=context, opts=llm_opts)
    return combined


def enrich_notes(
    notes: str,
    *,
    context: str,
    opts: LlmOptions | None = None,
    on_progress: Callable[[str], None] | None = None,
    cancel_event: Callable[[], bool] | None = None,
) -> str | None:
    if not context.strip():
        return None
    llm_opts = opts or options_from_config()

    def _cancelled() -> bool:
        return bool(cancel_event and cancel_event())

    def _enrich_once(section: str, ctx: str) -> str | None:
        if _cancelled():
            return None
        prompt = ENRICH_PROMPT.format(
            context=ctx[:50000] if ctx else "(none)",
            notes=section[:45000],
        )
        return generate(prompt, opts=llm_opts, timeout=300.0)

    if len(notes) <= 45000:
        sections = _split_h2_sections(notes)
        if len(sections) <= 1:
            return _enrich_once(notes, context)

    sections = _split_h2_sections(notes)
    if len(sections) <= 1:
        return _enrich_once(notes, context)

    enriched_parts: list[str] = []
    total = len(sections)
    for i, section in enumerate(sections, start=1):
        if _cancelled():
            break
        if on_progress:
            on_progress(f"Enriching section {i}/{total}…")
        ctx = reference_slice(context, i, total)
        part = _enrich_once(section, ctx)
        if part:
            enriched_parts.append(postprocess_markdown(part))

    if not enriched_parts:
        return None

    combined = "\n\n".join(enriched_parts)
    if len(combined) <= 45000 and not _cancelled():
        if on_progress:
            on_progress("Enriching — final stitch pass…")
        final = _enrich_once(combined, context)
        if final:
            return postprocess_markdown(final)
    return combined


def _estimate_total_steps(
    chunk_count: int,
    draft: str,
    *,
    refine_second_pass: bool,
    enrich_with_references: bool,
    fast_mode: bool,
    has_references: bool,
) -> int:
    if fast_mode:
        return chunk_count + 1
    steps = chunk_count
    if refine_second_pass:
        sections = _split_h2_sections(draft)
        if len(draft) <= 45000 or len(sections) <= 1:
            steps += 1
        else:
            steps += (len(sections) + 2) // 3
            if len(draft) > 45000:
                steps += 1
    if enrich_with_references and has_references:
        sections = _split_h2_sections(draft)
        if len(draft) <= 45000 and len(sections) <= 1:
            steps += 1
        else:
            steps += max(1, len(sections))
            steps += 1
    return steps + 1


def resolve_session_snapshots_dir(transcript_path: Path, session_dir: Path | None) -> Path | None:
    if session_dir and (session_dir / "snapshots").is_dir():
        snaps = session_dir / "snapshots"
        if any(snaps.glob("*.png")):
            return snaps
    parent = transcript_path.parent
    if (parent / "snapshots").is_dir() and any((parent / "snapshots").glob("*.png")):
        return parent / "snapshots"
    return None


def generate_notes_from_text(
    raw: str,
    *,
    title: str = "lecture",
    aggressive: bool = False,
    output_dir: Path | None = None,
    opts: LlmOptions | None = None,
    context_folder: str | Path | None = None,
    reference_materials: str = "",
    refine_second_pass: bool = True,
    enrich_with_references: bool = True,
    fast_mode: bool = False,
    snapshots_dir: Path | None = None,
    note_output_path: Path | None = None,
    on_progress: Callable[[str], None] | None = None,
    on_step: Callable[[int, int, str], None] | None = None,
    cancel_event: Callable[[], bool] | None = None,
    source_paths: list[Path] | None = None,
) -> tuple[Path, str]:
    cfg = load_config()
    if not llm_available(cfg):
        raise RuntimeError(
            "Local LLM is not enabled. Turn on LLM in settings and start Ollama or LM Studio."
        )

    def _cancelled() -> bool:
        return bool(cancel_event and cancel_event())

    step_current = 0
    step_total = 1

    def progress(msg: str) -> None:
        log.info(msg)
        if on_progress:
            on_progress(msg)

    def advance(msg: str) -> None:
        nonlocal step_current
        step_current += 1
        progress(msg)
        if on_step:
            on_step(step_current, step_total, msg)

    exclude = {p.resolve() for p in (source_paths or [])}
    context = load_context_folder(context_folder, exclude_paths=exclude) if context_folder else ""
    all_references = reference_materials
    if context:
        all_references = f"{reference_materials}\n\n---\n\n{context}" if reference_materials else context
    if all_references:
        progress(f"Reference materials loaded ({len(all_references):,} chars)")

    cleaned = parse_transcript(raw, aggressive=aggressive, preserve_snapshots=True)
    if not cleaned:
        raise ValueError("Transcript is empty after cleanup.")

    progress(f"Cleaned transcript: {len(cleaned.split())} words")

    if cfg.use_semantic_chunking:
        chunks = _semantic_chunk(
            cleaned,
            threshold=cfg.semantic_chunk_threshold,
        ) or chunk_by_words(cleaned, target_words=2000, overlap_words=250)
    else:
        chunks = chunk_by_words(cleaned, target_words=2000, overlap_words=250)
    if not chunks:
        chunks = [cleaned]

    llm_opts = opts or options_from_config(cfg)
    tagged_drafts: list[TaggedDraft] = []
    total = len(chunks)
    step_total = total + 1

    for i, chunk in enumerate(chunks, start=1):
        if _cancelled():
            raise RuntimeError("Summarization cancelled.")
        advance(f"Summarizing section {i}/{total} ({len(chunk.split())} words)…")
        ref_hint = reference_slice(all_references, i, total)
        section = summarize_chunk(
            chunk,
            aggressive=aggressive,
            reference_hint=ref_hint,
            opts=llm_opts,
        )
        if not section:
            raise RuntimeError(f"LLM returned empty response for section {i}.")
        draft = postprocess_markdown(section)
        tagged_drafts.append(TaggedDraft(draft=draft))

    # --- Tag extraction + pre-refine topic ordering ---
    if cfg.use_tag_extraction and not fast_mode:
        def _generate_tag(prompt: str, tag_opts: object) -> str:
            return generate(prompt, opts=tag_opts)

        progress("Extracting topic tags from chunk drafts…")
        for td in tagged_drafts:
            td.tags = extract_tags_for_draft(td.draft, _generate_tag, llm_opts)

        all_tag_groups = [td.tags for td in tagged_drafts]
        tag_map = normalize_tags(all_tag_groups)
        tagged_drafts = sort_drafts_by_topic(tagged_drafts, tag_map)
        progress(f"Topic sort complete — {len(set(tag_map.values()))} canonical topics")

        # Annotate with TOPICS: so REFINE can see semantic groupings
        sections: list[str] = [f"# {title.replace('_', ' ')}\n"]
        for td in tagged_drafts:
            sections.append(annotate_draft_with_topics(td))
    else:
        sections = [f"# {title.replace('_', ' ')}\n"] + [td.draft for td in tagged_drafts]

    body = "\n\n".join(sections)
    step_total = _estimate_total_steps(
        total,
        body,
        refine_second_pass=refine_second_pass and not fast_mode,
        enrich_with_references=enrich_with_references and not fast_mode,
        fast_mode=fast_mode,
        has_references=bool(all_references),
    )
    progress(f"Draft assembled — {len(body):,} chars from {total} sections")

    if fast_mode:
        body = strip_topics_annotations(body)
        progress("Fast mode — skipping refine and enrich passes.")
    elif refine_second_pass:
        if _cancelled():
            raise RuntimeError("Summarization cancelled.")
        advance("Refining notes (2nd pass — stitch topics, keep full depth)…")
        refined = refine_notes(body, title=title, context=all_references, opts=llm_opts)
        if refined:
            body = postprocess_markdown(strip_topics_annotations(refined))
        else:
            # Strip annotations from draft even if refine is skipped
            body = strip_topics_annotations(body)
            progress("Refine pass returned empty — keeping section draft.")

    if not fast_mode and enrich_with_references and all_references:
        if _cancelled():
            raise RuntimeError("Summarization cancelled.")
        advance("Enriching with Colab/PDF examples (3rd pass)…")

        def enrich_progress(msg: str) -> None:
            progress(msg)

        enriched = enrich_notes(
            body,
            context=all_references,
            opts=llm_opts,
            on_progress=enrich_progress,
            cancel_event=cancel_event,
        )
        if enriched:
            body = postprocess_markdown(enriched)
        else:
            progress("Enrich pass skipped — keeping refined draft.")

    out_root = output_dir or cfg.notes_path()
    out_root.mkdir(parents=True, exist_ok=True)
    if note_output_path:
        path = note_output_path
    else:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        safe_title = "".join(c if c.isalnum() or c in "-_ " else "_" for c in title)[:60].strip()
        safe_title = safe_title.replace(" ", "_") or "lecture"
        path = out_root / f"{safe_title}_{stamp}.md"

    if snapshots_dir and snapshots_dir.is_dir():
        if _cancelled():
            raise RuntimeError("Summarization cancelled.")
        advance(f"Embedding {len(list(snapshots_dir.glob('*.png')))} slide images…")
        body = inject_snapshot_images(body, snapshots_dir, note_path=path)
    else:
        advance("Writing notes file…")

    progress(
        f"Done — {len(body.split()):,} words, {count_mermaid_blocks(body)} mermaid, "
        f"{count_code_blocks(body)} code blocks"
    )

    path.write_text(body, encoding="utf-8")

    if cfg.inject_wikilinks:
        try:
            _inject_wikilinks(path, folder=out_root)
            # Re-read body in case wikilinks were injected
            body = path.read_text(encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            progress(f"Wikilink injection skipped: {exc}")

    return path, body


def generate_notes_from_file(
    transcript_path: Path,
    *,
    title: str | None = None,
    aggressive: bool = False,
    output_dir: Path | None = None,
    opts: LlmOptions | None = None,
    context_folder: str | Path | None = None,
    refine_second_pass: bool = True,
    enrich_with_references: bool = True,
    fast_mode: bool = False,
    session_dir: Path | None = None,
    on_progress: Callable[[str], None] | None = None,
) -> tuple[Path, str]:
    if not transcript_path.is_file():
        raise FileNotFoundError(f"Transcript not found: {transcript_path}")
    raw = load_source_file(transcript_path)
    note_title = title or transcript_path.stem.replace("_", " ")
    snaps = resolve_session_snapshots_dir(transcript_path, session_dir)
    if not aggressive and "live_captions" in transcript_path.name.lower():
        aggressive = True
    return generate_notes_from_text(
        raw,
        title=note_title,
        aggressive=aggressive,
        output_dir=output_dir,
        opts=opts,
        context_folder=context_folder,
        refine_second_pass=refine_second_pass,
        enrich_with_references=enrich_with_references,
        fast_mode=fast_mode,
        snapshots_dir=snaps,
        on_progress=on_progress,
    )


def list_transcripts(folder: Path | None = None) -> list[Path]:
    return list_source_files(folder)


def combine_transcript_files(paths: list[Path]) -> str:
    return combine_source_files(paths)


def generate_notes_from_files(
    transcript_paths: list[Path],
    *,
    title: str = "lecture",
    aggressive: bool = False,
    output_dir: Path | None = None,
    opts: LlmOptions | None = None,
    context_folder: str | Path | None = None,
    refine_second_pass: bool = True,
    enrich_with_references: bool = True,
    fast_mode: bool = False,
    session_dir: Path | None = None,
    on_progress: Callable[[str], None] | None = None,
    on_step: Callable[[int, int, str], None] | None = None,
    cancel_event: Callable[[], bool] | None = None,
) -> tuple[Path, str]:
    if not transcript_paths:
        raise ValueError("Select at least one source file.")

    transcript_text, reference_text, auto_aggressive = prepare_sources(transcript_paths)
    if auto_aggressive and not aggressive:
        aggressive = True

    if not context_folder and len(transcript_paths) > 1:
        parent = transcript_paths[0].parent
        if parent.is_dir():
            context_folder = str(parent)

    primary = transcript_paths[0]
    snaps = resolve_session_snapshots_dir(primary, session_dir)
    if not snaps:
        for p in transcript_paths:
            snaps = resolve_session_snapshots_dir(p, session_dir)
            if snaps:
                break

    def progress(msg: str) -> None:
        log.info(msg)
        if on_progress:
            on_progress(msg)

    if reference_text:
        progress(
            f"Using {len(transcript_paths)} file(s): transcript + "
            f"{len(reference_text.split())} words of PDF/Colab reference"
        )

    return generate_notes_from_text(
        transcript_text,
        title=title,
        aggressive=aggressive,
        output_dir=output_dir,
        opts=opts,
        context_folder=context_folder,
        reference_materials=reference_text,
        refine_second_pass=refine_second_pass,
        enrich_with_references=enrich_with_references,
        fast_mode=fast_mode,
        snapshots_dir=snaps,
        source_paths=transcript_paths,
        on_progress=on_progress,
        on_step=on_step,
        cancel_event=cancel_event,
    )
