"""Hybrid RAG + chunked lecture notes — corpus retrieve per segment, polish after each chunk."""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from backend.core.llm_job_context import llm_job
from backend.core.ollama_client import LlmOptions, ollama_available, ollama_generate
from backend.corpus.retrieve import (
    NOTES_RAG_SOURCE_TYPES,
    corpus_available,
    format_hits_for_prompt,
    hybrid_retrieve,
)
from backend.paths import NOTES_DIR
from backend.transcripts.asr_restore import maybe_restore_asr
from backend.transcripts.chunk_polish import finalize_full_note, polish_chunk_text_only
from backend.transcripts.cleanup import clean_transcript, count_code_blocks, count_mermaid_blocks, looks_like_live_captions, strip_llm_meta_preamble
from backend.transcripts.coherence import (
    extract_glossary_from_section,
    extract_heading,
    merge_glossary,
    parse_semantic_response,
    resolve_coherence_mode,
)
from backend.transcripts.narrative_audit import apply_narrative_marker, narrative_quality_report
from backend.transcripts.notes_generator import (
    REFINE_PROMPT,
    _effective_max_chunks,
    _escape_format_braces,
    _limit_chunks,
    _select_chunks,
    _split_oversized_chunks,
    placeholder_for_failed_chunk,
    summarize_chunk,
    resolve_transcript_path,
)
from backend.transcripts.path_utils import build_relative_path, normalize_folder_path

log = logging.getLogger(__name__)

# Transcripts longer than this use chunked hybrid RAG instead of single-shot grounded.
HYBRID_CHUNK_WORD_THRESHOLD = 1500
_CHUNK_QUERY_MAX = 280
_VERB_TOPIC_RE = re.compile(
    r"\b(?:discuss(?:es|ed|ing)?|cover(?:s|ed|ing)?|explain(?:s|ed|ing)?|"
    r"introduc(?:e|es|ed|ing)|analy(?:ze|zes|zed|zing)|derive(?:s|d|ing)|"
    r"show(?:s|ed|ing)|compare(?:s|d|ing)|focus(?:es|ed|ing)\s+on)\b\s+(?P<topic>[^.;:\n]{10,150})",
    re.IGNORECASE,
)
_LEADING_NOISE_RE = re.compile(r"^(?:in this (?:section|chunk|part),?\s*|today,?\s*|we\s+)", re.IGNORECASE)


def chunk_retrieval_query(chunk: str, topic: str = "") -> str:
    """Build an extractive retrieval query from topic + heading + first semantic phrase."""
    lines = [line.strip() for line in chunk.splitlines() if line.strip()]
    heading = ""
    first_sentence = ""

    for line in lines:
        if line.startswith("#"):
            heading = re.sub(r"^#+\s*", "", line).strip()
            continue
        if not first_sentence and len(line) >= 12:
            first_sentence = line
            break

    phrase = ""
    if first_sentence:
        m = _VERB_TOPIC_RE.search(first_sentence)
        if m:
            phrase = m.group("topic").strip(" -,:")
        else:
            phrase = first_sentence.split(".")[0].strip(" -,:")
        phrase = _LEADING_NOISE_RE.sub("", phrase).strip()

    parts: list[str] = []
    if topic.strip():
        parts.append(topic.strip())
    if heading:
        parts.append(heading)
    if phrase and phrase.lower() != heading.lower():
        parts.append(phrase[:140])

    query = " — ".join(p for p in parts if p).strip() or topic or heading or first_sentence or "lecture notes"
    return re.sub(r"\s+", " ", query)[:_CHUNK_QUERY_MAX]


def _write_note_file(
    markdown: str,
    *,
    title: str,
    folder_path: str = "",
) -> Path:
    folder = normalize_folder_path(folder_path)
    if folder:
        (NOTES_DIR / folder).mkdir(parents=True, exist_ok=True)
    from datetime import datetime, timezone

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe_title = "".join(c if c.isalnum() or c in "-_" else "_" for c in title)[:60].strip()
    safe_title = safe_title.replace(" ", "_") or "lecture"
    relative = build_relative_path(folder, f"{safe_title}_{stamp}.md")
    path = NOTES_DIR / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown, encoding="utf-8")
    return path


def generate_hybrid_grounded_notes(
    *,
    transcript_file: str,
    topic: str = "",
    folder_path: str = "",
    title: str | None = None,
    llm: LlmOptions | None = None,
    llm_tier: str | None = None,
    confirm_heavy_budget: bool = False,
    ingest_corpus: bool = True,
    on_progress: Callable[[str], None] | None = None,
    max_chunks: int = 12,
    fast_mode: bool = False,
    refine_second_pass: bool = False,
    llm_pause_sec: float = 0.0,
    subject_tags: list[str] | None = None,
    enrich_visuals: bool | None = None,
    pre_cleaned: str | None = None,
    restore_punctuation: bool = False,
    asr_backend: str = "recasepunc",
    note_style: str = "bullets",
    coherence_mode: str = "compact",
    semantic_threshold: float = 0.45,
    semantic_threshold_mode: str = "fixed",
    semantic_chunk_percentile: float = 95.0,
    narrative_judge: bool = False,
) -> dict[str, Any]:
    with llm_job(tier=llm_tier, task="notes_job"):
        return _generate_hybrid_grounded_notes_impl(
            transcript_file=transcript_file,
            topic=topic,
            folder_path=folder_path,
            title=title,
            llm=llm,
            llm_tier=llm_tier,
            confirm_heavy_budget=confirm_heavy_budget,
            ingest_corpus=ingest_corpus,
            on_progress=on_progress,
            max_chunks=max_chunks,
            fast_mode=fast_mode,
            refine_second_pass=refine_second_pass,
            llm_pause_sec=llm_pause_sec,
            subject_tags=subject_tags,
            enrich_visuals=enrich_visuals,
            pre_cleaned=pre_cleaned,
            restore_punctuation=restore_punctuation,
            asr_backend=asr_backend,
            note_style=note_style,
            coherence_mode=coherence_mode,
            semantic_threshold=semantic_threshold,
            semantic_threshold_mode=semantic_threshold_mode,
            semantic_chunk_percentile=semantic_chunk_percentile,
            narrative_judge=narrative_judge,
        )


def _generate_hybrid_grounded_notes_impl(
    *,
    transcript_file: str,
    topic: str = "",
    folder_path: str = "",
    title: str | None = None,
    llm: LlmOptions | None = None,
    confirm_heavy_budget: bool = False,
    ingest_corpus: bool = True,
    on_progress: Callable[[str], None] | None = None,
    max_chunks: int = 12,
    fast_mode: bool = False,
    refine_second_pass: bool = False,
    llm_pause_sec: float = 0.0,
    subject_tags: list[str] | None = None,
    enrich_visuals: bool | None = None,
    pre_cleaned: str | None = None,
    restore_punctuation: bool = False,
    asr_backend: str = "recasepunc",
    note_style: str = "bullets",
    coherence_mode: str = "compact",
    semantic_threshold: float = 0.45,
    semantic_threshold_mode: str = "fixed",
    semantic_chunk_percentile: float = 95.0,
    narrative_judge: bool = False,
    llm_tier: str | None = None,
) -> dict[str, Any]:
    """
    Chunked notes generation with hybrid RAG context per chunk.

    Flow per chunk (text-only, no visuals yet):
      hybrid_retrieve(query) → summarize_chunk(transcript, reference=corpus) → text polish
    Then merge → optional refine → finalize_full_note (visual enrich pass adds mermaid + code, then block repair).
    """
    if not corpus_available():
        raise RuntimeError("Corpus not available for hybrid grounded notes.")
    if not ollama_available(llm):
        raise RuntimeError(
            "LLM required for hybrid grounded notes. Configure the repo AI handler "
            "(OLLAMA_ENABLED=1, LLM_CLOUD_API_KEY, data/llm_tiers.json) or pass an explicit provider override."
        )

    transcript_path = resolve_transcript_path(transcript_file)
    note_title = (title or topic or transcript_path.stem.replace("_", " ")).strip()
    base_topic = topic or transcript_path.stem.replace("_", " ")

    def progress(msg: str) -> None:
        log.info("[hybrid] %s", msg)
        if on_progress:
            try:
                on_progress(msg)
            except Exception as exc:  # noqa: BLE001 — progress must never abort generation
                log.warning("on_progress callback failed: %s", exc)

    raw = transcript_path.read_text(encoding="utf-8")
    if pre_cleaned and pre_cleaned.strip():
        cleaned = pre_cleaned.strip()
    else:
        cleaned = clean_transcript(raw, aggressive=looks_like_live_captions(raw))
    if not cleaned.strip():
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
    progress(f"Hybrid RAG notes: {word_count:,} words — retrieving corpus context per chunk")

    from backend.transcripts._debug_agent_log import agent_log

    agent_log(
        location="hybrid_notes.py:before_select_chunks",
        message="hybrid_pre_chunk",
        data={"word_count": word_count, "note_style": note_style},
        hypothesis_id="H6",
    )
    t_sel = time.perf_counter()
    progress("Semantic chunking (loading embedding model if needed)…")
    # Hybrid grounded mode always uses semantic grouping (even when fast_mode is enabled).
    chunks = _select_chunks(
        cleaned,
        use_semantic_grouping=True,
        fast_mode=False,
        semantic_threshold=semantic_threshold,
        semantic_threshold_mode=semantic_threshold_mode,
        semantic_chunk_percentile=semantic_chunk_percentile,
    )
    agent_log(
        location="hybrid_notes.py:after_select_chunks",
        message="hybrid_post_chunk",
        data={"chunk_count": len(chunks), "elapsed_ms": int((time.perf_counter() - t_sel) * 1000)},
        hypothesis_id="H6",
    )
    progress(f"Semantic chunking done — {len(chunks)} segment(s); splitting if needed…")
    chunks = _split_oversized_chunks(chunks)
    cap = _effective_max_chunks(word_count, max_chunks, fast_mode=fast_mode)
    if len(chunks) > cap:
        progress(f"Merging {len(chunks)} segments -> {cap} hybrid passes...")
        chunks = _limit_chunks(chunks, max_chunks=cap)

    sections: list[str] = [f"# {note_title.replace('_', ' ')}\n"]
    citation_ids: list[str] = []
    chunk_meta: list[dict[str, Any]] = []
    total = len(chunks)
    glossary = ""
    prior_heading = ""
    running_notes = ""
    from backend.transcripts.coherence import SEQUENTIAL_CHAR_LIMIT

    for i, chunk in enumerate(chunks, start=1):
        query = chunk_retrieval_query(chunk, base_topic)
        log.info("[hybrid] chunk %d/%d query=%r", i, total, query[:120])
        hits = hybrid_retrieve(
            query,
            subject_tags=subject_tags,
            source_types=list(NOTES_RAG_SOURCE_TYPES),
            top_k=6,
        )
        ref = format_hits_for_prompt(hits, max_chars=9000) if hits else "(no corpus hits — transcript only)"
        for h in hits:
            cid = h.get("chunk_id")
            if cid and cid not in citation_ids:
                citation_ids.append(str(cid))

        progress(f"Chunk {i}/{total}: retrieve ({len(hits)} hits) -> LLM -> polish...")
        if (
            effective_coherence in ("sequential", "cloud_heavy")
            and i > 1
            and len(running_notes) > SEQUENTIAL_CHAR_LIMIT
        ):
            progress("Sequential mode: document too large — switching to compact append")
            effective_coherence = "compact"

        section = summarize_chunk(
            chunk,
            reference_hint=ref,
            llm=llm,
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
            log.warning("[hybrid] Chunk %d/%d failed after retries — inserting placeholder", i, total)
            progress(f"Chunk {i}/{total} unavailable — keeping raw excerpt in notes…")
            section = placeholder_for_failed_chunk(chunk, index=i, total=total)
        section = polish_chunk_text_only(section)
        if hits:
            cite_line = " ".join(f"<!-- cite: {h.get('chunk_id')} -->" for h in hits[:2] if h.get("chunk_id"))
            if cite_line and cite_line not in section:
                section = f"{section.rstrip()}\n{cite_line}\n"

        if effective_coherence in ("sequential", "cloud_heavy"):
            notes_part, gloss_part = parse_semantic_response(section)
            running_notes = notes_part or section
            glossary = merge_glossary(glossary, gloss_part)
            sections = [f"# {note_title.replace('_', ' ')}\n", running_notes]
        else:
            glossary = merge_glossary(glossary, extract_glossary_from_section(section))
            prior_heading = extract_heading(section) or prior_heading
            sections.append(section)
        chunk_meta.append({"index": i, "query": query, "hit_count": len(hits)})

        pause = max(0.0, float(llm_pause_sec))
        if pause > 0 and i < total:
            progress(f"Pausing {pause:.0f}s before next chunk…")
            time.sleep(pause)

    body = "\n\n".join(sections)
    if refine_second_pass:
        progress("Refining merged notes (second pass)…")
        refined = ollama_generate(
            REFINE_PROMPT.format(body=_escape_format_braces(body[:24_000])),
            timeout=240.0,
            llm=llm,
            task="notes_refine",
            confirm_heavy_budget=confirm_heavy_budget,
        )
        if refined and refined.strip():
            body = polish_chunk_text_only(strip_llm_meta_preamble(refined))

    audit = narrative_quality_report(body)
    if audit.marker:
        progress(f"Narrative quality heuristic: {audit.score}/5 ({audit.marker})")
        body = apply_narrative_marker(body, audit)

    body = finalize_full_note(
        body,
        repair_blocks=True,
        use_llm_repair=False,
        enrich_visuals=enrich_visuals if enrich_visuals is not None else not fast_mode,
        llm=llm,
        on_progress=progress,
    )
    progress(f"Done — {count_mermaid_blocks(body)} mermaid, {count_code_blocks(body)} code blocks")

    notes_path = _write_note_file(body, title=note_title, folder_path=folder_path)
    handoff = None
    if ingest_corpus:
        from backend.corpus.handoff import ingest_lecture_handoff

        handoff = ingest_lecture_handoff(transcript_path=transcript_path, note_path=notes_path)

    rel = notes_path.relative_to(NOTES_DIR).as_posix()
    return {
        "mode": "hybrid_grounded",
        "filename": rel,
        "notes_path": str(notes_path),
        "markdown": body,
        "chunk_count": len(chunks),
        "corpus_hits_total": sum(m["hit_count"] for m in chunk_meta),
        "citations": citation_ids[:24],
        "chunks": chunk_meta,
        "corpus_handoff": handoff,
    }


def should_use_hybrid_chunked(
    transcript_path: Path,
    *,
    word_threshold: int = HYBRID_CHUNK_WORD_THRESHOLD,
    pre_cleaned: str | None = None,
) -> bool:
    if pre_cleaned and pre_cleaned.strip():
        return len(pre_cleaned.split()) >= word_threshold
    try:
        raw = transcript_path.read_text(encoding="utf-8")
    except OSError:
        return False
    cleaned = clean_transcript(raw, aggressive=looks_like_live_captions(raw))
    return len(cleaned.split()) >= word_threshold


def generate_grounded_notes_smart(
    *,
    transcript_file: str,
    topic: str = "",
    folder_path: str = "",
    title: str | None = None,
    llm: LlmOptions | None = None,
    llm_tier: str | None = None,
    confirm_heavy_budget: bool = False,
    ingest_corpus: bool = True,
    on_progress: Callable[[str], None] | None = None,
    force_hybrid: bool = False,
    **kwargs: Any,
) -> dict[str, Any]:
    """Pick hybrid chunked RAG vs single-shot grounded based on transcript length."""
    transcript_path = resolve_transcript_path(transcript_file)
    pre_cleaned = kwargs.get("pre_cleaned")
    use_hybrid = force_hybrid or should_use_hybrid_chunked(
        transcript_path,
        pre_cleaned=pre_cleaned if isinstance(pre_cleaned, str) else None,
    )
    if use_hybrid and corpus_available() and ollama_available(llm):
        hybrid_keys = (
            "max_chunks",
            "fast_mode",
            "refine_second_pass",
            "llm_pause_sec",
            "subject_tags",
            "enrich_visuals",
            "pre_cleaned",
            "restore_punctuation",
            "asr_backend",
            "note_style",
            "coherence_mode",
            "semantic_threshold",
            "semantic_threshold_mode",
            "semantic_chunk_percentile",
            "narrative_judge",
        )
        hybrid_kwargs = {k: v for k, v in kwargs.items() if k in hybrid_keys}
        return generate_hybrid_grounded_notes(
            transcript_file=transcript_file,
            topic=topic,
            folder_path=folder_path,
            title=title,
            llm=llm,
            llm_tier=llm_tier,
            confirm_heavy_budget=confirm_heavy_budget,
            ingest_corpus=ingest_corpus,
            on_progress=on_progress,
            **hybrid_kwargs,
        )
    from backend.corpus.grounded_notes import generate_grounded_notes_single_shot

    enrich_visuals = kwargs.get("enrich_visuals", True)
    if kwargs.get("fast_mode"):
        enrich_visuals = False

    return generate_grounded_notes_single_shot(
        transcript_file=transcript_file,
        topic=topic,
        folder_path=folder_path,
        title=title,
        llm=llm,
        llm_tier=llm_tier,
        confirm_heavy_budget=confirm_heavy_budget,
        ingest_corpus=ingest_corpus,
        enrich_visuals=bool(enrich_visuals),
    )
