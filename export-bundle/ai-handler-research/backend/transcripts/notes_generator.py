"""Generate markdown lecture notes from cleaned transcripts via Ollama."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import time

from backend.core.llm_job_context import llm_job
from backend.core.ollama_client import LlmOptions, ollama_available, ollama_generate
from backend.paths import NOTES_DIR, TRANSCRIPTS_DIR
from backend.transcripts.asr_restore import maybe_restore_asr
from backend.transcripts.chunk_polish import finalize_full_note, polish_chunk_text_only
from backend.transcripts.cleanup import (
    chunk_by_words,
    clean_transcript,
    count_code_blocks,
    count_mermaid_blocks,
    postprocess_markdown,
    strip_llm_meta_preamble,
)
from backend.transcripts.coherence import (
    build_narrative_chunk_prompt,
    build_sequential_prompt,
    coherence_task,
    extract_glossary_from_section,
    extract_heading,
    merge_glossary,
    parse_semantic_response,
    resolve_coherence_mode,
)
from backend.transcripts.narrative_audit import apply_narrative_marker, narrative_quality_report
from backend.transcripts.path_utils import build_relative_path, normalize_folder_path
from backend.transcripts.semantic_chunker import semantic_chunk
from backend.transcripts.snapshots import append_snapshot_gallery, inject_snapshot_images
from backend.transcripts.semantic_grouper import group_transcript, groups_from_word_chunks
from backend.transcripts.sources import load_context_folder, prepare_sources, reference_slice, resolve_source_path

log = logging.getLogger(__name__)


def _escape_format_braces(text: str) -> str:
    """Prevent str.format KeyError when transcript/reference contains `{...}`."""
    return text.replace("{", "{{").replace("}", "}}")


REFINE_PROMPT = """Polish these lecture notes into one cohesive markdown document.
- Fix duplicate headings and merge overlapping bullets
- Keep existing code blocks intact; do not add new diagrams here
- Output markdown only (no preamble, no meta commentary about polishing or merging)
- Do not add a conclusion about what you changed

{body}
"""

CHUNK_PROMPT = f"""You are creating lecture study notes from a live-caption transcript chunk.

Rules:
- Output markdown ONLY (no preamble like "Here's your summary").
- Start with a ## heading for the main topic in this chunk.
- Write 3-5 bullet key points (concise lecture notes, not verbatim transcript).
- Text only: do NOT add mermaid diagrams or ``` code blocks — visuals and code are added in a final enrich pass on the full document.
- If the chunk discusses an algorithm or code, describe it in bullets (name, inputs, steps, output) so the enrich pass can generate the block later.
- Preserve ![Slide N](...) image lines if they appear in the transcript chunk.
- Filler words are already removed.

Reference material (weave in examples when relevant):
{{reference}}

Transcript chunk:
{{chunk}}
{{context_block}}
"""

NARRATIVE_CHUNK_PROMPT = CHUNK_PROMPT  # legacy alias; narrative uses build_narrative_chunk_prompt()

GenerateFn = Callable[[str], str | None]

# LM Studio / local models: keep prompts within context; split upstream instead of hard cut.
PROMPT_CHUNK_CHAR_LIMIT = 48_000
PROMPT_CHUNK_WORD_TARGET = 4_000


def _slice_chunk_for_prompt(chunk: str, *, max_chars: int = PROMPT_CHUNK_CHAR_LIMIT) -> tuple[str, bool]:
    """Fit chunk into prompt; use head+tail only when still too large after word-splitting."""
    text = chunk.strip()
    if len(text) <= max_chars:
        return text, False
    head = int(max_chars * 0.65)
    tail = max(0, max_chars - head - 120)
    omitted = len(text) - head - tail
    return (
        text[:head]
        + f"\n\n[... {omitted:,} characters omitted from middle of this segment ...]\n\n"
        + text[-tail:],
        True,
    )


def _split_oversized_chunks(
    chunks: list[str],
    *,
    max_words: int = PROMPT_CHUNK_WORD_TARGET,
    max_chars: int = PROMPT_CHUNK_CHAR_LIMIT,
) -> list[str]:
    """Break merged mega-chunks so the LLM sees the full lecture, not a 12k-char prefix."""
    out: list[str] = []
    for chunk in chunks:
        words = len(chunk.split())
        if words <= max_words and len(chunk) <= max_chars:
            out.append(chunk)
            continue
        target = min(2500, max_words)
        parts = chunk_by_words(chunk, target_words=target, overlap_words=150)
        out.extend(parts if parts else [chunk])
    return out


def _effective_max_chunks(word_count: int, cap: int, *, fast_mode: bool) -> int:
    """Scale LLM passes with lecture length; avoid crushing 100k+ word transcripts into 8 passes."""
    cap = max(4, int(cap))
    minimum = max(cap, (word_count + 3499) // 3500)
    if word_count > 80_000:
        minimum = max(minimum, 20 if fast_mode else 24)
    elif word_count > 40_000:
        minimum = max(minimum, 14 if fast_mode else 18)
    ceiling = 32 if fast_mode else max(cap, 28)
    return min(max(minimum, 8 if fast_mode else cap), ceiling)


def _resolve_context_folder(context_folder: str) -> Path | None:
    raw = Path(context_folder.strip())
    if raw.is_dir():
        return raw
    candidate = NOTES_DIR / normalize_folder_path(context_folder.strip())
    return candidate if candidate.is_dir() else None


def _merge_reference_materials(existing: str, extra: str) -> str:
    if not extra.strip():
        return existing
    if not existing.strip():
        return extra.strip()
    return f"{existing.strip()}\n\n---\n\n{extra.strip()}"


def _generate(
    prompt: str,
    *,
    llm: LlmOptions | None,
    generate_fn: GenerateFn | None = None,
    timeout: float = 180.0,
    task: str = "notes_chunk",
    confirm_heavy_budget: bool = False,
    empty_retries: int = 2,
    empty_retry_pause_sec: float = 2.0,
) -> str | None:
    attempts = max(1, int(empty_retries) + 1)
    last: str | None = None
    for attempt in range(attempts):
        if generate_fn is not None:
            last = generate_fn(prompt)
        else:
            last = ollama_generate(
                prompt,
                timeout=timeout,
                llm=llm,
                task=task,
                confirm_heavy_budget=confirm_heavy_budget,
            )
        if last is not None and last.strip():
            return last
        if attempt < attempts - 1 and empty_retry_pause_sec > 0:
            time.sleep(empty_retry_pause_sec)
    return last


def summarize_chunk(
    chunk: str,
    *,
    aggressive: bool = False,
    reference_hint: str = "",
    llm: LlmOptions | None = None,
    generate_fn: GenerateFn | None = None,
    note_style: str = "bullets",
    semantic_glossary: str = "",
    prior_heading: str = "",
    chunk_index: int = 1,
    coherence_mode: str = "compact",
    running_notes: str = "",
    llm_tier: str | None = None,
    confirm_heavy_budget: bool = False,
) -> str | None:
    ref = reference_hint[:6000] if reference_hint.strip() else "(none)"
    chunk_text, _truncated = _slice_chunk_for_prompt(chunk)
    style = (note_style or "bullets").strip().lower()
    mode = resolve_coherence_mode(coherence_mode, llm_tier=llm_tier)
    is_first = chunk_index <= 1

    if style == "narrative":
        if mode in ("sequential", "cloud_heavy") and not is_first and running_notes.strip():
            prompt = build_sequential_prompt(
                chunk=chunk_text,
                reference=ref,
                running_notes=running_notes,
                glossary=semantic_glossary,
                is_first=False,
            )
        else:
            prompt = build_narrative_chunk_prompt(
                chunk=chunk_text,
                reference=ref,
                is_first=is_first,
                glossary=semantic_glossary,
                prior_heading=prior_heading,
            )
    else:
        context_block = ""
        if semantic_glossary.strip() or prior_heading.strip():
            context_block = (
                f"\n\nPrevious topic: {prior_heading or '(none)'}\n"
                f"Terms already defined:\n{semantic_glossary[:400] or '(none)'}"
            )
        body = CHUNK_PROMPT.format(
            chunk=_escape_format_braces(chunk_text),
            reference=_escape_format_braces(ref),
            context_block=_escape_format_braces(context_block),
        )
        prompt = body

    if aggressive:
        prompt = (
            "This is a noisy live-caption dump with repeated partial snapshots. "
            "Extract only clean lecture content as markdown notes.\n\n" + prompt
        )

    task = coherence_task(mode) if style == "narrative" and mode == "cloud_heavy" else "notes_chunk"
    raw = _generate(
        prompt,
        llm=llm,
        generate_fn=generate_fn,
        task=task,
        confirm_heavy_budget=confirm_heavy_budget,
    )
    if raw and raw.strip():
        return strip_llm_meta_preamble(raw.strip())
    return raw


def placeholder_for_failed_chunk(chunk: str, *, index: int, total: int = 0) -> str:
    """Preserve progress when the LLM fails a chunk after all retries."""
    excerpt = chunk.strip()[:800]
    if len(chunk.strip()) > 800:
        excerpt += "…"
    label = f"Chunk {index}/{total}" if total else f"Chunk {index}"
    return (
        f"## {label} (summary unavailable)\n\n"
        "*LLM returned empty after retries — raw excerpt preserved below.*\n\n"
        f"{excerpt}\n"
    )


def _limit_chunks(chunks: list[str], *, max_chunks: int = 12) -> list[str]:
    """Avoid dozens of sequential LLM calls on long transcripts."""
    if len(chunks) <= max_chunks:
        return chunks
    size = (len(chunks) + max_chunks - 1) // max_chunks
    merged: list[str] = []
    for i in range(0, len(chunks), size):
        merged.append("\n\n".join(chunks[i : i + size]))
    return merged[:max_chunks]


def _select_chunks(
    cleaned: str,
    *,
    use_semantic_grouping: bool = True,
    fast_mode: bool = False,
    semantic_threshold: float = 0.45,
    semantic_threshold_mode: str = "fixed",
    semantic_chunk_percentile: float = 95.0,
) -> list[str]:
    if fast_mode:
        chunks = chunk_by_words(cleaned, target_words=5000, overlap_words=100)
        return chunks or [cleaned]

    if use_semantic_grouping:
        mode = (semantic_threshold_mode or "fixed").strip().lower()
        if mode not in ("fixed", "percentile"):
            mode = "fixed"
        from backend.transcripts._debug_agent_log import agent_log

        agent_log(
            location="notes_generator.py:_select_chunks",
            message="select_semantic_chunker",
            data={"mode": mode, "words": len(cleaned.split())},
            hypothesis_id="H5",
        )
        chunks = semantic_chunk(
            cleaned,
            threshold=semantic_threshold,
            threshold_mode=mode,  # type: ignore[arg-type]
            percentile=semantic_chunk_percentile,
        )
        if chunks:
            log.info("Chunk selection: semantic_chunker (%d segments)", len(chunks))
            return chunks
        groups = group_transcript(cleaned)
        if groups:
            log.info("Chunk selection: semantic_grouper (%d segments)", len(groups))
            return [g.text for g in groups]
        log.info("Semantic chunking unavailable; using word-chunk fallback")

    chunks = chunk_by_words(cleaned)
    if chunks:
        return chunks
    word_groups = groups_from_word_chunks(cleaned, target_words=2500)
    return [g.text for g in word_groups] if word_groups else [cleaned]


def generate_notes_from_text(
    raw: str,
    *,
    title: str = "lecture",
    aggressive: bool = False,
    llm: LlmOptions | None = None,
    llm_tier: str | None = None,
    confirm_heavy_budget: bool = False,
    folder_path: str = "",
    output_dir: Path | None = None,
    note_output_path: Path | None = None,
    on_progress: Callable[[str], None] | None = None,
    generate_fn: GenerateFn | None = None,
    already_cleaned: bool = False,
    reference_materials: str = "",
    transcript_stem: str | None = None,
    use_semantic_grouping: bool = True,
    fast_mode: bool = False,
    refine_second_pass: bool = False,
    enrich_with_references: bool = True,
    use_tag_extraction: bool = False,
    context_folder: str | None = None,
    max_chunks: int = 12,
    llm_pause_sec: float = 0.0,
    exclude_context_paths: set[Path] | None = None,
    **kwargs: object,
) -> tuple[Path, str]:
    with llm_job(tier=llm_tier, task="notes_job"):
        return _generate_notes_from_text_unwrapped(
            raw,
            title=title,
            aggressive=aggressive,
            llm=llm,
            confirm_heavy_budget=confirm_heavy_budget,
            folder_path=folder_path,
            output_dir=output_dir,
            note_output_path=note_output_path,
            on_progress=on_progress,
            generate_fn=generate_fn,
            already_cleaned=already_cleaned,
            reference_materials=reference_materials,
            transcript_stem=transcript_stem,
            use_semantic_grouping=use_semantic_grouping,
            fast_mode=fast_mode,
            refine_second_pass=refine_second_pass,
            enrich_with_references=enrich_with_references,
            use_tag_extraction=use_tag_extraction,
            context_folder=context_folder,
            max_chunks=max_chunks,
            llm_pause_sec=llm_pause_sec,
            exclude_context_paths=exclude_context_paths,
            llm_tier=llm_tier,
            **kwargs,
        )


def _generate_notes_from_text_unwrapped(
    raw: str,
    *,
    title: str = "lecture",
    aggressive: bool = False,
    llm: LlmOptions | None = None,
    confirm_heavy_budget: bool = False,
    folder_path: str = "",
    output_dir: Path | None = None,
    note_output_path: Path | None = None,
    on_progress: Callable[[str], None] | None = None,
    generate_fn: GenerateFn | None = None,
    already_cleaned: bool = False,
    reference_materials: str = "",
    transcript_stem: str | None = None,
    use_semantic_grouping: bool = True,
    fast_mode: bool = False,
    refine_second_pass: bool = False,
    enrich_with_references: bool = True,
    use_tag_extraction: bool = False,
    context_folder: str | None = None,
    max_chunks: int = 12,
    llm_pause_sec: float = 0.0,
    exclude_context_paths: set[Path] | None = None,
    llm_tier: str | None = None,
    **kwargs: object,
) -> tuple[Path, str]:
    enrich_visuals = kwargs.pop("enrich_visuals", None)
    if enrich_visuals is not None and not isinstance(enrich_visuals, bool):
        enrich_visuals = bool(enrich_visuals)
    restore_punctuation = bool(kwargs.pop("restore_punctuation", False))
    asr_backend = str(kwargs.pop("asr_backend", "recasepunc") or "recasepunc")
    note_style = str(kwargs.pop("note_style", "bullets") or "bullets")
    coherence_mode = str(kwargs.pop("coherence_mode", "compact") or "compact")
    semantic_threshold = float(kwargs.pop("semantic_threshold", 0.45) or 0.45)
    semantic_threshold_mode = str(kwargs.pop("semantic_threshold_mode", "fixed") or "fixed")
    semantic_chunk_percentile = float(kwargs.pop("semantic_chunk_percentile", 95.0) or 95.0)
    narrative_judge = bool(kwargs.pop("narrative_judge", False))
    ctx = (context_folder or "").strip() or str(kwargs.pop("context_folder", "") or "").strip() or None
    exclude = {p.resolve() for p in (exclude_context_paths or set())}
    extra_exclude = kwargs.pop("exclude_context_paths", None)
    if extra_exclude:
        exclude.update(Path(p).resolve() for p in extra_exclude)
    if ctx:
        folder = _resolve_context_folder(ctx)
        if folder:
            extra_ref = load_context_folder(folder, exclude_paths=exclude or None)
            reference_materials = _merge_reference_materials(reference_materials, extra_ref)

    if generate_fn is None and not ollama_available(llm):
        raise RuntimeError(
            "LLM is not available. Set OLLAMA_ENABLED=1 in repo .env and configure "
            "data/llm_tiers.json (AI handler), or start a local provider."
        )

    def progress(msg: str) -> None:
        log.info(msg)
        if on_progress:
            on_progress(msg)

    cleaned = raw if already_cleaned else clean_transcript(raw, aggressive=aggressive)
    if not cleaned:
        raise ValueError("Transcript is empty after cleanup.")

    cleaned = maybe_restore_asr(
        cleaned,
        raw,
        enabled=restore_punctuation,
        auto_for_live_captions=restore_punctuation,
        backend=asr_backend,
    )

    effective_coherence = resolve_coherence_mode(coherence_mode, llm_tier=str(llm_tier or ""))

    word_count = len(cleaned.split())
    char_count = len(cleaned)
    progress(f"Cleaned transcript: {word_count:,} words ({char_count:,} chars)")
    if reference_materials.strip():
        progress(f"Reference context: {len(reference_materials.split()):,} words")
    elif ctx:
        progress("Context folder set but no reference text loaded (check PDF/md paths)")
    else:
        progress("No reference context folder — transcript only")

    chunks = _select_chunks(
        cleaned,
        use_semantic_grouping=use_semantic_grouping,
        fast_mode=fast_mode,
        semantic_threshold=semantic_threshold,
        semantic_threshold_mode=semantic_threshold_mode,
        semantic_chunk_percentile=semantic_chunk_percentile,
    )
    chunks = _split_oversized_chunks(chunks)
    cap = _effective_max_chunks(word_count, max_chunks, fast_mode=fast_mode)
    if len(chunks) > cap:
        progress(
            f"Merging {len(chunks)} segments → {cap} passes "
            f"(raise max_llm_chunks in config for more detail)…"
        )
        chunks = _limit_chunks(chunks, max_chunks=cap)
        chunks = _split_oversized_chunks(chunks)
        if len(chunks) > cap:
            progress(f"Re-split merged segments -> {len(chunks)} LLM passes (full coverage)")

    sections: list[str] = [f"# {title.replace('_', ' ')}\n"]
    total = len(chunks)
    glossary = ""
    prior_heading = ""
    running_notes = ""
    from backend.transcripts.coherence import SEQUENTIAL_CHAR_LIMIT

    for i, chunk in enumerate(chunks, start=1):
        chunk_words = len(chunk.split())
        prompt_chunk, truncated = _slice_chunk_for_prompt(chunk)
        sent_chars = len(prompt_chunk)
        trunc_note = " — WARNING: prompt truncated" if truncated else ""
        progress(
            f"Summarizing chunk {i}/{total} "
            f"({chunk_words:,} words, {sent_chars:,} chars to LLM){trunc_note}…"
        )
        ref_hint = reference_materials
        if enrich_with_references and reference_materials.strip() and total > 1:
            ref_hint = reference_slice(reference_materials, i, total)

        if (
            effective_coherence in ("sequential", "cloud_heavy")
            and i > 1
            and len(running_notes) > SEQUENTIAL_CHAR_LIMIT
        ):
            progress("Sequential mode: document too large — switching to compact append for remaining chunks")
            effective_coherence = "compact"

        section = summarize_chunk(
            chunk,
            aggressive=aggressive,
            reference_hint=ref_hint,
            llm=llm,
            generate_fn=generate_fn,
            note_style=note_style,
            semantic_glossary=glossary,
            prior_heading=prior_heading,
            chunk_index=i,
            coherence_mode=effective_coherence,
            running_notes=running_notes,
            llm_tier=str(llm_tier or ""),
            confirm_heavy_budget=confirm_heavy_budget,
        )
        if not section or not section.strip():
            log.warning("Chunk %d/%d failed after retries — inserting placeholder", i, total)
            progress(f"Chunk {i}/{total} unavailable — keeping raw excerpt in notes…")
            section = placeholder_for_failed_chunk(chunk, index=i, total=total)
        section = polish_chunk_text_only(section)

        if effective_coherence in ("sequential", "cloud_heavy"):
            notes_part, gloss_part = parse_semantic_response(section)
            running_notes = notes_part or section
            glossary = merge_glossary(glossary, gloss_part)
            if i == 1:
                sections = [f"# {title.replace('_', ' ')}\n", running_notes]
            else:
                sections = [f"# {title.replace('_', ' ')}\n", running_notes]
        else:
            glossary = merge_glossary(glossary, extract_glossary_from_section(section))
            prior_heading = extract_heading(section) or prior_heading
            sections.append(section)
        if use_tag_extraction:
            from backend.transcripts.tag_engine import (
                TaggedDraft,
                annotate_draft_with_topics,
                extract_tags_for_draft,
            )

            def _tag_generate(prompt: str, _opts: object) -> str | None:
                return _generate(prompt, llm=llm, generate_fn=generate_fn)

            tags = extract_tags_for_draft(section, _tag_generate, None)
            section = annotate_draft_with_topics(TaggedDraft(draft=section, tags=tags))
        sections.append(section)
        pause = max(0.0, float(llm_pause_sec))
        if pause > 0 and i < total:
            progress(f"Pausing {pause:.0f}s before next chunk (CPU/GPU cool-down)…")
            time.sleep(pause)

    body = "\n\n".join(sections)
    if refine_second_pass:
        progress("Refining notes (second pass)…")
        refined = _generate(
            REFINE_PROMPT.format(body=_escape_format_braces(body[:24_000])),
            llm=llm,
            generate_fn=generate_fn,
            timeout=240.0,
            task="notes_refine",
            confirm_heavy_budget=confirm_heavy_budget,
        )
        if refined:
            body = polish_chunk_text_only(strip_llm_meta_preamble(refined))

    audit = narrative_quality_report(body)
    if audit.marker:
        progress(f"Narrative quality heuristic: {audit.score}/5 ({audit.marker})")
        body = apply_narrative_marker(body, audit)
    if narrative_judge and generate_fn is not None:
        from backend.transcripts.narrative_audit import llm_narrative_judge

        judge_score = llm_narrative_judge(body, generate_fn=generate_fn)
        if judge_score is not None:
            progress(f"Narrative judge score: {judge_score}/5")
            if judge_score < 3 and "NARRATIVE_LOW" not in body:
                body = f"<!-- NARRATIVE_LOW: judge score {judge_score}/5 -->\n\n{body}"
    if transcript_stem:
        body = append_snapshot_gallery(body, transcript_stem)
    body = finalize_full_note(
        body,
        repair_blocks=True,
        use_llm_repair=False,
        enrich_visuals=enrich_visuals if enrich_visuals is not None else not fast_mode,
        llm=llm,
        on_progress=progress,
    )
    progress(
        f"Done — {count_mermaid_blocks(body)} mermaid, {count_code_blocks(body)} code blocks"
    )

    out_root = output_dir or NOTES_DIR
    out_root.mkdir(parents=True, exist_ok=True)
    folder = normalize_folder_path(folder_path)
    if folder:
        (out_root / folder).mkdir(parents=True, exist_ok=True)

    if note_output_path:
        path = note_output_path
    else:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        safe_title = "".join(c if c.isalnum() or c in "-_" else "_" for c in title)[:60].strip()
        safe_title = safe_title.replace(" ", "_") or "lecture"
        relative = build_relative_path(folder, f"{safe_title}_{stamp}.md")
        path = out_root / relative if output_dir else NOTES_DIR / relative

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path, body


def generate_notes_from_sources(
    source_paths: list[Path],
    *,
    title: str = "lecture",
    aggressive: bool = False,
    llm: LlmOptions | None = None,
    folder_path: str = "",
    on_progress: Callable[[str], None] | None = None,
    **kwargs: object,
) -> tuple[Path, str]:
    if not source_paths:
        raise ValueError("Select at least one source file.")

    transcript_text, reference_text, auto_aggressive, _manifest = prepare_sources(source_paths)
    if auto_aggressive and not aggressive:
        aggressive = True
    stem = source_paths[0].stem if source_paths else None

    extra_ref = str(kwargs.pop("reference_materials", "") or "")
    if reference_text:
        extra_ref = f"{extra_ref}\n\n---\n\n{reference_text}".strip() if extra_ref else reference_text

    return generate_notes_from_text(
        transcript_text,
        title=title,
        aggressive=aggressive,
        llm=llm,
        folder_path=folder_path,
        reference_materials=extra_ref,
        transcript_stem=stem,
        on_progress=on_progress,
        **kwargs,
    )


def generate_notes_from_file(
    transcript_path: Path,
    *,
    title: str | None = None,
    aggressive: bool = False,
    llm: LlmOptions | None = None,
    llm_tier: str | None = None,
    confirm_heavy_budget: bool = False,
    folder_path: str = "",
    reference_paths: list[Path] | None = None,
    on_progress: Callable[[str], None] | None = None,
    **kwargs: object,
) -> tuple[Path, str]:
    if not transcript_path.is_file():
        raise FileNotFoundError(f"Transcript not found: {transcript_path}")

    note_title = title or transcript_path.stem.replace("_", " ")

    context_folder = kwargs.pop("context_folder", None)
    if context_folder:
        folder = _resolve_context_folder(str(context_folder))
        if folder:
            extra_ref = load_context_folder(folder, exclude_paths={transcript_path.resolve()})
            kwargs["reference_materials"] = _merge_reference_materials(
                str(kwargs.get("reference_materials") or ""),
                extra_ref,
            )

    if reference_paths:
        paths = [transcript_path, *reference_paths]
        return generate_notes_from_sources(
            paths,
            title=note_title,
            aggressive=aggressive,
            llm=llm,
            folder_path=folder_path,
            on_progress=on_progress,
            **kwargs,
        )

    raw = transcript_path.read_text(encoding="utf-8")
    raw = inject_snapshot_images(raw, transcript_path.stem)
    return generate_notes_from_text(
        raw,
        title=note_title,
        aggressive=aggressive,
        llm=llm,
        llm_tier=llm_tier,
        confirm_heavy_budget=confirm_heavy_budget,
        folder_path=folder_path,
        transcript_stem=transcript_path.stem,
        on_progress=on_progress,
        **kwargs,
    )


def resolve_transcript_path(filename: str) -> Path:
    path = TRANSCRIPTS_DIR / filename
    if not path.resolve().is_relative_to(TRANSCRIPTS_DIR.resolve()):
        raise ValueError("Invalid transcript path.")
    return path


def resolve_notes_path(relative_path: str) -> Path:
    return resolve_source_path(relative_path)


def list_transcripts() -> list[dict]:
    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    items = []
    for p in sorted(TRANSCRIPTS_DIR.glob("*.txt"), key=lambda x: x.stat().st_mtime, reverse=True):
        items.append({"filename": p.name, "size_bytes": p.stat().st_size, "modified": p.stat().st_mtime})
    return items


def list_notes() -> list[dict]:
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    items = []
    for p in sorted(NOTES_DIR.rglob("*.md"), key=lambda x: x.stat().st_mtime, reverse=True):
        rel = p.relative_to(NOTES_DIR).as_posix()
        items.append({"filename": rel, "size_bytes": p.stat().st_size, "modified": p.stat().st_mtime})
    return items
