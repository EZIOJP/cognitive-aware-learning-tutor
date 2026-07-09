"""Corpus RAG availability for Transcript Notes Studio."""

from __future__ import annotations

from dataclasses import dataclass

from transcript_studio.config import AppConfig
from transcript_studio.gateway_llm import (
    default_llm_tier,
    gateway_status_line,
    llm_generate_available,
    llm_generate_reachable,
    uses_gateway,
)
from transcript_studio.llm_client import LlmOptions, llm_available, llm_reachable, options_from_config


@dataclass(frozen=True)
class RagStatus:
    corpus_available: bool
    llm_available: bool
    rag_ready: bool
    legacy_forced: bool = False
    retrieval_backend: str = "unknown"
    llm_tier: str = "medium"
    gateway_mode: bool = True

    @property
    def vector_degraded(self) -> bool:
        return self.rag_ready and self.retrieval_backend == "sqlite"

    @property
    def mode_label(self) -> str:
        if self.legacy_forced:
            return "Legacy (forced)"
        if self.rag_ready:
            if self.vector_degraded:
                return "RAG degraded (SQLite vectors)"
            if self.gateway_mode:
                return f"RAG (corpus + AI handler {self.llm_tier})"
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
            if self.vector_degraded:
                return (
                    "RAG degraded — dense retrieval fell back to SQLite (Qdrant locked or unavailable). "
                    "Close other Python/uvicorn processes using data/corpus/qdrant, then restart Studio. "
                    "Notes still generate but textbook matching may be weaker."
                )
            if self.gateway_mode:
                return (
                    "RAG active via AI handler — notes use tier chains from data/llm_tiers.json "
                    "(Gemini/cloud when configured in repo .env). Textbook chunks only during retrieval."
                )
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
        if self.gateway_mode:
            return (
                "RAG off — AI handler has no reachable provider. "
                "Set OLLAMA_ENABLED=1 and LLM_CLOUD_API_KEY in repo .env, or pick a manual provider override."
            )
        return "RAG off — LLM offline. Legacy summarization will be used."

    @property
    def banner_style(self) -> str:
        if self.vector_degraded:
            return "warn"
        if self.rag_ready and not self.legacy_forced:
            return "ok"
        if not self.corpus_available or not self.llm_available:
            return "warn"
        return "muted"


def _retrieval_backend_safe() -> str:
    try:
        from backend.corpus.retrieve import retrieval_backend

        return retrieval_backend()
    except Exception:
        return "unknown"


def _llm_checks(cfg: AppConfig, opts: LlmOptions | None = None) -> tuple[bool, bool]:
    from transcript_studio.gateway_llm import gateway_reachable, uses_gateway

    if gateway_reachable():
        return True, True
    if uses_gateway(cfg):
        return False, False
    if opts is None:
        opts = options_from_config(cfg)
    ok = llm_available(cfg) and llm_reachable(opts)
    return ok, llm_reachable(opts)


def check_rag_status(cfg: AppConfig, *, legacy_forced: bool = False) -> RagStatus:
    corpus_ok = False
    try:
        from backend.corpus.retrieve import corpus_available

        corpus_ok = corpus_available()
    except Exception:
        corpus_ok = False

    llm_ok, _ = _llm_checks(cfg)
    rag_ready = corpus_ok and llm_ok and not legacy_forced
    return RagStatus(
        corpus_available=corpus_ok,
        llm_available=llm_ok,
        rag_ready=rag_ready,
        legacy_forced=legacy_forced,
        retrieval_backend=_retrieval_backend_safe(),
        llm_tier=default_llm_tier(cfg),
        gateway_mode=uses_gateway(cfg),
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

    llm_ok, _ = _llm_checks(cfg, opts)
    rag_ready = corpus_ok and llm_ok and not legacy_forced
    return RagStatus(
        corpus_available=corpus_ok,
        llm_available=llm_ok,
        rag_ready=rag_ready,
        legacy_forced=legacy_forced,
        retrieval_backend=_retrieval_backend_safe(),
        llm_tier=default_llm_tier(cfg),
        gateway_mode=uses_gateway(cfg),
    )


def llm_status_line(cfg: AppConfig) -> str:
    if uses_gateway(cfg):
        return gateway_status_line(cfg)
    opts = options_from_config(cfg)
    ok = llm_reachable(opts)
    return f"LLM: {'● reachable' if ok else '○ offline'} — {cfg.llm_model}"
