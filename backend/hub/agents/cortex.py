"""Cortex-style hub router — classify intent and delegate to specialists."""

from __future__ import annotations

import re

from sqlalchemy.orm import Session

from backend.core.ollama_client import ollama_generate, ollama_available
from backend.hub.agents.schemas import HubChatResponse
from backend.hub.agents import session_rag
from backend.hub.agents.specialists import (
    run_chat_specialist,
    run_coding_specialist,
    run_corpus_specialist,
    run_pdf_rag_specialist,
    run_search_specialist,
    run_study_specialist,
)

_VALID_AGENTS = frozenset({"auto", "chat", "coding", "corpus", "search", "pdf_rag", "study", "vision"})


def _classify_agent(prompt: str) -> str:
    if not ollama_available():
        return "chat"
    raw = ollama_generate(
        f"""Classify this student message into exactly ONE word: chat, search, coding, corpus, or study.

Message: {prompt[:500]}

Reply with only the word.""",
        task="hub_router",
        timeout=30.0,
    )
    if not raw:
        return "chat"
    word = re.sub(r"[^a-z_]", "", raw.strip().lower())
    if word in ("search", "coding", "corpus", "study", "chat"):
        return word
    return "chat"


def resolve_agent(
    requested: str,
    *,
    prompt: str,
    content_type: str | None = None,
    has_session_pdf: bool = False,
) -> tuple[str, list[str]]:
    trace: list[str] = []
    agent = (requested or "auto").strip().lower()
    if agent not in _VALID_AGENTS:
        agent = "auto"

    if agent != "auto":
        trace.append(f"manual:{agent}")
        return agent, trace

    if content_type:
        if content_type.startswith("image/"):
            trace.append("file:image→chat")
            return "chat", trace
        if content_type == "application/pdf":
            trace.append("file:pdf→pdf_rag")
            return "pdf_rag", trace

    if has_session_pdf:
        trace.append("session:pdf→pdf_rag")
        return "pdf_rag", trace

    classified = _classify_agent(prompt)
    trace.append(f"classifier→{classified}")
    return classified, trace


def run_hub_chat(
    *,
    db: Session,
    user_id: int,
    hub_context: dict,
    messages: list[dict[str, str]],
    agent: str = "auto",
    conversation_id: str | None = None,
    llm_tier: str | None = None,
    file_bytes: bytes | None = None,
    file_name: str | None = None,
    content_type: str | None = None,
) -> HubChatResponse:
    session_id = conversation_id or f"user-{user_id}"
    last_query = messages[-1]["content"] if messages else ""

    if file_bytes and file_name:
        count = session_rag.ingest_upload(session_id, file_name, file_bytes, content_type or "")
        trace = [f"ingested:{file_name} ({count} chunks)"]
        if not last_query.strip():
            return HubChatResponse(
                reply=f"Uploaded **{file_name}** ({count} chunks). Ask a question about it.",
                agent_used="pdf_rag",
                trace=trace,
            )
    else:
        trace = []

    has_pdf = bool(session_rag.session_filename(session_id))
    resolved, route_trace = resolve_agent(
        agent,
        prompt=last_query,
        content_type=content_type,
        has_session_pdf=has_pdf,
    )
    trace.extend(route_trace)

    try:
        if resolved == "coding":
            reply, sources = run_coding_specialist(
                messages, hub_context=hub_context, last_query=last_query, llm_tier=llm_tier
            )
        elif resolved == "corpus":
            reply, sources = run_corpus_specialist(messages, llm_tier=llm_tier)
        elif resolved == "pdf_rag":
            reply, sources = run_pdf_rag_specialist(
                messages, session_id=session_id, llm_tier=llm_tier
            )
        elif resolved == "search":
            reply, sources = run_search_specialist(
                messages,
                hub_context=hub_context,
                db=db,
                user_id=user_id,
                llm_tier=llm_tier,
            )
        elif resolved == "study":
            reply, sources = run_study_specialist(
                messages, hub_context=hub_context, llm_tier=llm_tier
            )
        else:
            reply, sources = run_chat_specialist(
                messages,
                hub_context=hub_context,
                db=db,
                user_id=user_id,
                llm_tier=llm_tier,
            )
            resolved = "chat"
    except Exception as exc:
        return HubChatResponse(
            reply=f"Hub agent failed ({exc}). Check AI Control Center → Test connections.",
            agent_used=resolved,
            source="template",
            llm_available=False,
            trace=trace,
        )

    return HubChatResponse(
        reply=reply,
        agent_used=resolved,
        trace=trace,
        rag_sources=sources,
    )
