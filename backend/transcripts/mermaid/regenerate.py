"""Regenerate a mermaid block via local LLM."""
from __future__ import annotations

import re

from backend.core.ollama_client import LlmOptions, ollama_available, ollama_generate
from backend.transcripts.mermaid.pipeline import layout_safe_mermaid_source, sanitize_mermaid_source
from backend.transcripts.mermaid.prompts import MERMAID_GENERATION_RULES, MERMAID_SYSTEM_PROMPT

_FENCE_RE = re.compile(r"^```(?:\w+)?\s*\n?", re.MULTILINE)
_TRAILING_FENCE_RE = re.compile(r"\n?```\s*$", re.MULTILINE)


def _strip_fences(raw: str) -> str:
    text = raw.strip()
    text = _FENCE_RE.sub("", text, count=1)
    text = _TRAILING_FENCE_RE.sub("", text)
    return text.strip()


def _build_prompt(
    *,
    content: str,
    error: str | None,
    note_context: str | None,
    mode: str,
) -> str:
    error_line = f"\nMermaid parse/render error (fix this): {error}" if error else ""
    if error and "layout" in error.lower():
        error_line += (
            "\nLayout fix: shorten labels under 40 chars, use etc not ..., index -1 not W[-1]."
        )
    context = ""
    if note_context:
        context = f"\n\nContext (topic only):\n---\n{note_context[:3500]}\n---"
    rules = f"\n{MERMAID_GENERATION_RULES}"
    if mode == "polish":
        return f"""Polish this Mermaid diagram. Return ONLY valid Mermaid.{rules}
- Output EXACTLY ONE diagram{error_line}{context}

Draft:
{content.strip() or "(empty)"}
"""
    return f"""Fix this broken Mermaid diagram. Return ONLY valid Mermaid.{rules}
- Output EXACTLY ONE diagram{error_line}{context}

Broken source:
{content.strip() or "(empty)"}
"""


def regenerate_mermaid(
    content: str,
    error: str | None = None,
    note_context: str | None = None,
    mode: str = "fix",
    llm: LlmOptions | None = None,
) -> str:
    if not ollama_available(llm):
        raise RuntimeError(
            "LLM is not reachable. Set OLLAMA_ENABLED=1 and start LM Studio/Ollama."
        )
    raw = ollama_generate(
        _build_prompt(content=content, error=error, note_context=note_context, mode=mode),
        timeout=90.0,
        llm=llm,
        system_prompt=MERMAID_SYSTEM_PROMPT,
    )
    if not raw:
        raise RuntimeError("LLM returned no content.")
    return layout_safe_mermaid_source(raw)
