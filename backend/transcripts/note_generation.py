"""Unified notes generation — RAG-first when corpus + LLM are available."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.core.ollama_client import LlmOptions, ollama_available
from backend.corpus.retrieve import corpus_available


def rag_notes_available(*, llm: LlmOptions | None = None) -> bool:
    return bool(corpus_available() and ollama_available(llm))


def resolve_grounding(
    mode: str,
    rag_result: dict[str, Any] | None,
) -> tuple[str, str | None]:
    """
    Return (grounding_status, grounding_reason).

    grounded = textbook RAG contributed citations; degraded = transcript-only / no textbook hits.
    """
    if not corpus_available():
        return "degraded", "corpus_unavailable"
    if mode.startswith("legacy"):
        return "degraded", "no_textbook_chunks_retrieved"
    if mode == "assemble" or mode == "lecture_first":
        citations = list((rag_result or {}).get("citations") or [])
        if citations:
            return "grounded", None
        return "degraded", "lecture_only_or_no_gated_hits"
    citations = []
    if rag_result:
        citations = list(rag_result.get("citations") or [])
        chunk_count = int(rag_result.get("chunk_count") or 0)
        if not citations and chunk_count <= 0:
            # hybrid may store citation ids; also check chunk_meta hit counts
            meta = rag_result.get("chunk_meta") or []
            hits = sum(int(m.get("hit_count") or 0) for m in meta if isinstance(m, dict))
            if hits <= 0:
                return "degraded", "no_textbook_chunks_retrieved"
    if rag_result and citations:
        return "grounded", None
    if rag_result and str(rag_result.get("mode") or "").startswith(("hybrid", "grounded")):
        meta = rag_result.get("chunk_meta") or []
        hits = sum(int(m.get("hit_count") or 0) for m in meta if isinstance(m, dict))
        if hits > 0 or int(rag_result.get("chunk_count") or 0) > 0:
            return "grounded", None
        return "degraded", "no_textbook_chunks_retrieved"
    return "degraded", "no_textbook_chunks_retrieved"


def generate_notes_unified(
    *,
    transcript_path: Path,
    transcript_file: str,
    title: str,
    topic: str | None = None,
    folder_path: str = "",
    llm: LlmOptions | None = None,
    llm_tier: str | None = None,
    confirm_heavy_budget: bool = False,
    ingest_corpus: bool = True,
    force_legacy: bool = False,
    assemble_mode: bool = False,
    **legacy_kwargs: Any,
) -> tuple[Path, str, str, dict[str, Any] | None]:
    """
    Returns (note_path, markdown, mode, rag_result_or_none).

    Default path when ``assemble_mode``: lecture-first extractive notes (no LLM rewrite).
    Textbooks attach only via gated retrieve. LLM+RAG hybrid only when assemble_mode is False.
    """
    subject = topic or title
    on_progress = legacy_kwargs.get("on_progress")

    if assemble_mode:
        from backend.transcripts.assemble_notes import assemble_notes_from_transcript

        result = assemble_notes_from_transcript(
            transcript_file=transcript_file,
            topic=subject,
            folder_path=folder_path,
            title=title,
            ingest_corpus=ingest_corpus,
            on_progress=on_progress if callable(on_progress) else None,
            max_chunks=int(legacy_kwargs.get("max_chunks") or 20),
            pre_cleaned=legacy_kwargs.get("pre_cleaned")
            if isinstance(legacy_kwargs.get("pre_cleaned"), (str, type(None)))
            else None,
        )
        path = Path(result["notes_path"])
        content = result.get("markdown") or path.read_text(encoding="utf-8")
        mode = str(result.get("mode") or "lecture_first")
        status, reason = resolve_grounding(mode, result)
        result["grounding_status"] = status
        result["grounding_reason"] = reason
        return path, content, mode, result

    if not force_legacy and rag_notes_available(llm=llm):
        from backend.transcripts.hybrid_notes import generate_grounded_notes_smart

        rag_kwargs = {
            k: legacy_kwargs[k]
            for k in (
                "max_chunks",
                "fast_mode",
                "refine_second_pass",
                "llm_pause_sec",
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
            if k in legacy_kwargs
        }
        result = generate_grounded_notes_smart(
            transcript_file=transcript_file,
            topic=subject,
            folder_path=folder_path,
            title=title,
            llm=llm,
            llm_tier=llm_tier,
            confirm_heavy_budget=confirm_heavy_budget,
            ingest_corpus=ingest_corpus,
            on_progress=on_progress if callable(on_progress) else None,
            **rag_kwargs,
        )
        path = Path(result["notes_path"])
        content = result.get("markdown") or path.read_text(encoding="utf-8")
        mode = str(result.get("mode") or "grounded")
        status, reason = resolve_grounding(mode, result)
        result["grounding_status"] = status
        result["grounding_reason"] = reason
        return path, content, mode, result

    from backend.transcripts.notes_generator import generate_notes_from_file

    path, content = generate_notes_from_file(
        transcript_path,
        title=title,
        llm=llm,
        llm_tier=llm_tier,
        confirm_heavy_budget=confirm_heavy_budget,
        folder_path=folder_path,
        **legacy_kwargs,
    )
    reason = "corpus_unavailable" if not corpus_available() else "no_textbook_chunks_retrieved"
    if force_legacy:
        reason = "force_legacy"
    meta = {
        "grounding_status": "degraded",
        "grounding_reason": reason,
        "mode": "legacy",
    }
    return path, content, "legacy", meta
