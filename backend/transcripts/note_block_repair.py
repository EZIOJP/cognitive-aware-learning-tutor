"""Repair all broken mermaid/code fenced blocks in a note (local sanitize + LLM one-by-one)."""

from __future__ import annotations

from typing import Any

from backend.core.ollama_client import LlmOptions, ollama_available
from backend.transcripts.block_regenerate import regenerate_block
from backend.transcripts.note_document import (
    apply_block_replacements,
    apply_mermaid_layout_safe,
    block_surrounding_context,
    list_fenced_blocks,
    mermaid_still_broken,
    prepare_note_markdown,
)

_CODE_LANGS = frozenset({"python", "py", "javascript", "js", "typescript", "ts"})
_BROKEN_CODE = frozenset({"", "undefined", "null", "[object object]"})


def _is_broken_code(content: str) -> bool:
    return content.strip().lower() in _BROKEN_CODE


def repair_all_blocks(
    markdown: str,
    *,
    llm: LlmOptions | None = None,
    use_llm: bool = True,
) -> tuple[str, list[dict[str, Any]]]:
    """
    Fix fenced mermaid + code blocks one-by-one.
    1) Local mermaid layout-safe sanitize on every mermaid block
    2) LLM (Gemma/Ollama) for blocks still broken or empty code
    """
    base = prepare_note_markdown(markdown)
    replacements: dict[int, str] = {}
    details: list[dict[str, Any]] = []
    blocks = list_fenced_blocks(base)

    for block in blocks:
        idx = block.index
        lang = block.lang
        content = block.content
        new_content = content
        method: str | None = None

        if lang == "mermaid":
            sanitized = apply_mermaid_layout_safe(content)
            if sanitized != content:
                new_content = sanitized
                method = "sanitize"

            if mermaid_still_broken(new_content):
                if not use_llm:
                    details.append(
                        {"index": idx, "lang": lang, "method": method or "skipped", "status": "still_broken"}
                    )
                    if method:
                        replacements[idx] = new_content
                    continue
                if not ollama_available(llm):
                    details.append(
                        {
                            "index": idx,
                            "lang": lang,
                            "method": method or "none",
                            "status": "llm_unavailable",
                        }
                    )
                    if method:
                        replacements[idx] = new_content
                    continue
                ctx = block_surrounding_context(base, idx)
                new_content = regenerate_block(
                    block_type="mermaid",
                    language="mermaid",
                    content=new_content,
                    note_context=ctx,
                    error="Mermaid diagram has invalid syntax (edge labels, stadium nodes, or special characters).",
                    mode="fix",
                    llm=llm,
                )
                new_content = apply_mermaid_layout_safe(new_content)
                method = f"{method}+llm" if method else "llm"

        elif lang in _CODE_LANGS and _is_broken_code(content):
            if not use_llm:
                details.append({"index": idx, "lang": lang, "method": "skipped", "status": "empty_code"})
                continue
            if not ollama_available(llm):
                details.append({"index": idx, "lang": lang, "method": "none", "status": "llm_unavailable"})
                continue
            ctx = block_surrounding_context(base, idx)
            code_lang = "python" if lang in ("python", "py") else "javascript"
            new_content = regenerate_block(
                block_type="code",
                language=code_lang,
                content=content,
                note_context=ctx,
                error="Code block is empty or placeholder (undefined).",
                mode="fix",
                llm=llm,
            )
            method = "llm"

        if new_content != content:
            replacements[idx] = new_content
            details.append({"index": idx, "lang": lang, "method": method or "unknown", "status": "fixed"})

    result = apply_block_replacements(base, replacements)
    return result, details
