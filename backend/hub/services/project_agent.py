"""Project Agent — Gemma chat with full codebase context (pairs with Cursor)."""

from __future__ import annotations

import json

from backend.core.ollama_client import ollama_available, ollama_generate
from backend.hub.services.codebase_agent import retrieve_codebase_knowledge

PROJECT_AGENT_SYSTEM = """You are the Project Agent for Cognitive-Aware Learning Tutor.
You work WITH the student AND Cursor AI (their coding assistant) to finish the website.

You receive JSON with:
- snapshot: frontend routes, API routes, top CSS classes, open TODOs, study pipeline flags
- matched_files: real source excerpts from the repo based on the student's question
- student_context: study metrics, lecture notes summary, quiz backlog (when provided)
- cursor_pairing_hint: how to phrase tasks for Cursor

Your job:
1. Read matched_files and snapshot — cite REAL paths (e.g. src/pages/study/LectureNotesPage.tsx)
2. When asked about CSS/UI: reference actual class names from css_top_classes (gloss-panel, study-library-glass, etc.)
3. Suggest SMALL incremental tasks (one PR-sized change), not giant rewrites
4. For each task give: goal, files to touch, what to tell Cursor in one sentence
5. Flag gaps in study_pipeline (live captions → notes → quiz → review loop)
6. Be warm and direct. No buzzword "optimize" — say what to change and why

When you don't see a file in matched_files, say so and suggest keywords to search.
Never invent file paths that aren't in the context."""


def project_agent_available() -> bool:
    return bool(ollama_available())


def chat_with_project_agent(
    messages: list[dict[str, str]],
    *,
    hub_context: dict,
    last_query: str = "",
) -> str:
    if not project_agent_available():
        raise RuntimeError("Local LLM is not enabled. Set OLLAMA_ENABLED=1 and start LM Studio.")

    codebase = retrieve_codebase_knowledge(last_query)
    context = {
        "student_context": {
            "username": hub_context.get("student", {}).get("username"),
            "today": hub_context.get("today"),
            "suggested_priorities": hub_context.get("suggested_priorities"),
            "lecture_notes": hub_context.get("lecture_notes"),
            "vocab": hub_context.get("vocab"),
            "quiz_backlog": hub_context.get("quiz_backlog", []),
            "knowledge_index": hub_context.get("knowledge_index"),
        },
        "codebase": codebase,
    }

    history_lines: list[str] = []
    for msg in messages[-12:]:
        role = msg.get("role", "user")
        content = (msg.get("content") or "").strip()
        if content:
            history_lines.append(f"{role.upper()}: {content}")

    prompt = f"""Conversation:
{chr(10).join(history_lines)}

Full context (JSON):
{json.dumps(context, indent=2, default=str)}

Reply as the Project Agent. Use bullet lists for tasks. End with ONE recommended next action."""

    raw = ollama_generate(prompt, system_prompt=PROJECT_AGENT_SYSTEM, timeout=120.0)
    if not raw:
        raise ValueError("Empty response from local LLM")
    return raw.strip()[:6000]
