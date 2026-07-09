"""Unified notes generation — RAG-first when corpus + LLM are available."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.core.ollama_client import LlmOptions, ollama_available
from backend.corpus.retrieve import corpus_available


def rag_notes_available(*, llm: LlmOptions | None = None) -> bool:
    return bool(corpus_available() and ollama_available(llm))


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
    **legacy_kwargs: Any,
) -> tuple[Path, str, str, dict[str, Any] | None]:
    """
    Returns (note_path, markdown, mode, rag_result_or_none).

    Uses hybrid/single-shot RAG when corpus + LLM are ready; otherwise legacy summarization.
    """
    subject = topic or title

    if not force_legacy and rag_notes_available(llm=llm):
        from backend.transcripts.hybrid_notes import generate_grounded_notes_smart

        on_progress = legacy_kwargs.get("on_progress")
        rag_kwargs = {
            k: legacy_kwargs[k]
            for k in (
                "max_chunks",
                "fast_mode",
                "refine_second_pass",
                "llm_pause_sec",
                "enrich_visuals",
                "pre_cleaned",
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
        return path, content, str(result.get("mode") or "grounded"), result

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
    return path, content, "legacy", None
