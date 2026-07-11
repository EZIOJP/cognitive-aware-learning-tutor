"""Specialist agents wrapping existing hub services."""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.hub.services.local_coach import chat_with_coach, local_llm_available
from backend.hub.services.project_agent import chat_with_project_agent, project_agent_available
from backend.hub.services.coach_knowledge import retrieve_coach_knowledge
from backend.corpus.retrieve import hybrid_retrieve, format_hits_for_prompt, corpus_available
from backend.core.ollama_client import ollama_generate, ollama_available
from backend.hub.agents.session_rag import retrieve as session_retrieve
from backend.hub.agents.web_search import format_search_context, tavily_search


def run_chat_specialist(
    messages: list[dict[str, str]],
    *,
    hub_context: dict,
    db: Session,
    user_id: int,
    llm_tier: str | None = None,
    extra_context: str = "",
) -> tuple[str, list[str]]:
    last_query = messages[-1]["content"] if messages else ""
    hub_context = dict(hub_context)
    hub_context["knowledge_base"] = retrieve_coach_knowledge(db, user_id, last_query)
    if extra_context:
        hub_context["web_search_context"] = extra_context
    if not local_llm_available():
        raise RuntimeError("LLM not available")
    reply = chat_with_coach(messages, hub_context=hub_context, llm_tier=llm_tier)
    sources: list[str] = []
    kb = hub_context.get("knowledge_base") or {}
    for note in (kb.get("lecture_notes") or [])[:3]:
        title = note.get("title") or note.get("topic")
        if title:
            sources.append(str(title))
    return reply, sources


def run_coding_specialist(
    messages: list[dict[str, str]],
    *,
    hub_context: dict,
    last_query: str,
    llm_tier: str | None = None,
) -> tuple[str, list[str]]:
    if not project_agent_available():
        raise RuntimeError("LLM not available")
    reply = chat_with_project_agent(
        messages, hub_context=hub_context, last_query=last_query, llm_tier=llm_tier
    )
    return reply, []


def run_corpus_specialist(
    messages: list[dict[str, str]],
    *,
    llm_tier: str | None = None,
) -> tuple[str, list[str]]:
    if not ollama_available():
        raise RuntimeError("LLM not available")
    query = messages[-1]["content"] if messages else ""
    if not query.strip():
        return "Ask a question about your lecture corpus.", []
    if not corpus_available():
        return "Corpus is not built yet. Ingest lectures first.", []
    hits = hybrid_retrieve(query, top_k=6)
    context = format_hits_for_prompt(hits, max_chars=6000)
    prompt = f"""Student question: {query}

Corpus excerpts:
{context}

Answer using only the excerpts. Cite lecture/topic when possible. Be concise and study-focused."""
    reply = ollama_generate(prompt, task="corpus_qa", tier=llm_tier, timeout=120.0)
    sources = [str(h.get("source_title") or h.get("document_id") or "") for h in hits[:5]]
    return (reply or "No answer generated.").strip(), [s for s in sources if s]


def run_pdf_rag_specialist(
    messages: list[dict[str, str]],
    *,
    session_id: str,
    llm_tier: str | None = None,
) -> tuple[str, list[str]]:
    if not ollama_available():
        raise RuntimeError("LLM not available")
    query = messages[-1]["content"] if messages else ""
    chunks = session_retrieve(session_id, query, top_k=5)
    if not chunks:
        return "Upload a PDF first, then ask a question about it.", []
    context = "\n\n---\n\n".join(chunks)
    prompt = f"""Question: {query}

Document excerpts:
{context}

Answer from the document only. If the answer is not in the excerpts, say so."""
    reply = ollama_generate(prompt, task="corpus_qa", tier=llm_tier, timeout=120.0)
    return (reply or "No answer generated.").strip(), [f"session:{session_id}"]


def run_search_specialist(
    messages: list[dict[str, str]],
    *,
    hub_context: dict,
    db: Session,
    user_id: int,
    llm_tier: str | None = None,
) -> tuple[str, list[str]]:
    query = messages[-1]["content"] if messages else ""
    results = tavily_search(query)
    if not results:
        return (
            "Web search is unavailable. Add TAVILY_API_KEY in Settings → AI Control Center.",
            [],
        )
    context = format_search_context(results)
    return run_chat_specialist(
        messages,
        hub_context=hub_context,
        db=db,
        user_id=user_id,
        llm_tier=llm_tier,
        extra_context=context,
    )


def run_study_specialist(
    messages: list[dict[str, str]],
    *,
    hub_context: dict,
    llm_tier: str | None = None,
) -> tuple[str, list[str]]:
    _ = llm_tier
    query = messages[-1]["content"] if messages else ""
    topic = query.strip()[:120] or "your topic"
    notes = hub_context.get("lecture_notes") or {}
    recent = notes.get("recent_titles") or notes.get("topics") or []
    if isinstance(recent, list):
        preview = ", ".join(str(t) for t in recent[:5] if t)
    else:
        preview = ""
    count = notes.get("count") if isinstance(notes, dict) else len(recent) if isinstance(recent, list) else 0
    reply = (
        f"For **{topic}**, use Study Flow: grounded notes → quiz → SRS.\n\n"
        f"Open **/study-flow** and enter that topic. "
        f"Your library has {count or 0} indexed lecture note(s)"
        + (f" (recent: {preview})" if preview else "")
        + ".\n\n"
        "Use **Corpus** mode here for direct RAG Q&A, or **Chat** for coaching."
    )
    return reply, []
