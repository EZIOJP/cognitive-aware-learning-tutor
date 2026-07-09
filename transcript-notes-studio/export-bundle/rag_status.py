"""Corpus RAG availability for Transcript Notes Studio."""

from __future__ import annotations

from dataclasses import dataclass

from transcript_studio.config import AppConfig
from transcript_studio.llm_client import LlmOptions, llm_available, llm_reachable, options_from_config


@dataclass(frozen=True)
class RagStatus:
    corpus_available: bool
    llm_available: bool
    rag_ready: bool
    legacy_forced: bool = False

    @property
    def mode_label(self) -> str:
        if self.legacy_forced:
            return "Legacy (forced)"
        if self.rag_ready:
            return "RAG (corpus + LLM)"
        if not self.corpus_available:
            return "Legacy (no corpus)"
        if not self.llm_available:
            return "Legacy (LLM offline)"
        return "Legacy"

    @property
    def banner_text(self) -> str:
        if self.legacy_forced:
            return "Advanced: Legacy pipeline enabled — RAG disabled for this run."
        if self.rag_ready:
            return (
                "RAG active — notes retrieve textbook chunks only (not transcripts/notes in the index). "
                "Hybrid per-segment for long transcripts. Extra indexed lectures are for quiz/review after save."
            )
        if not self.corpus_available:
            return (
                "RAG off — corpus not built. Use Knowledge base (RAG) on the Generate step "
                "(Quick init: textbooks + MML only), or run scripts\\run_corpus_ingest.bat. "
                "Context folder still adds PDF/md references (not corpus RAG)."
            )
        return "RAG off — start LM Studio/Ollama. Legacy summarization will be used."

    @property
    def banner_style(self) -> str:
        if self.rag_ready and not self.legacy_forced:
            return "ok"
        if not self.corpus_available or not self.llm_available:
            return "warn"
        return "muted"


def check_rag_status(cfg: AppConfig, *, legacy_forced: bool = False) -> RagStatus:
    corpus_ok = False
    try:
        from backend.corpus.retrieve import corpus_available

        corpus_ok = corpus_available()
    except Exception:
        corpus_ok = False

    opts = options_from_config(cfg)
    llm_ok = llm_available(cfg) and llm_reachable(opts)
    rag_ready = corpus_ok and llm_ok and not legacy_forced
    return RagStatus(
        corpus_available=corpus_ok,
        llm_available=llm_ok,
        rag_ready=rag_ready,
        legacy_forced=legacy_forced,
    )


def check_rag_with_opts(
    cfg: AppConfig,
    opts: LlmOptions | None = None,
    *,
    legacy_forced: bool = False,
) -> RagStatus:
    corpus_ok = False
    try:
        from backend.corpus.retrieve import corpus_available

        corpus_ok = corpus_available()
    except Exception:
        corpus_ok = False

    if opts is None:
        opts = options_from_config(cfg)

    llm_ok = llm_available(cfg) and llm_reachable(opts)
    rag_ready = corpus_ok and llm_ok and not legacy_forced
    return RagStatus(
        corpus_available=corpus_ok,
        llm_available=llm_ok,
        rag_ready=rag_ready,
        legacy_forced=legacy_forced,
    )
