"""Repair all broken mermaid/code fenced blocks in a note (local sanitize + LLM one-by-one)."""

from __future__ import annotations

import re
from typing import Any

from backend.core.ollama_client import LlmOptions, ollama_available
from backend.transcripts.block_regenerate import regenerate_block
from backend.transcripts.cleanup import sanitize_mermaid_source

_FENCE_BLOCK_RE = re.compile(r"```(\w*)[^\S\r\n]*\r?\n([\s\S]*?)```", re.MULTILINE)
_CODE_LANGS = frozenset({"python", "py", "javascript", "js", "typescript", "ts"})
_BROKEN_CODE = frozenset({"", "undefined", "null", "[object object]"})
_FENCE_PLACEHOLDER_RE = re.compile(r"```[\w]*[^\S\r\n]*\r?\n[\s\S]*?```", re.MULTILINE)


def _list_fenced_blocks(markdown: str) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for m in _FENCE_BLOCK_RE.finditer(markdown):
        blocks.append(
            {
                "index": len(blocks),
                "lang": (m.group(1) or "text").lower(),
                "content": m.group(2).rstrip("\n"),
                "start": m.start(),
                "end": m.end(),
            }
        )
    return blocks


def _format_fence(lang: str, body: str) -> str:
    lang = lang.strip()
    if lang and lang != "text":
        return f"```{lang}\n{body.strip()}\n```"
    return f"```\n{body.strip()}\n```"


def _apply_block_replacements(markdown: str, replacements: dict[int, str]) -> str:
    if not replacements:
        return markdown
    blocks = _list_fenced_blocks(markdown)
    parts: list[str] = []
    last = 0
    for block in blocks:
        parts.append(markdown[last : block["start"]])
        body = replacements.get(block["index"], block["content"])
        parts.append(_format_fence(block["lang"], body))
        last = block["end"]
    parts.append(markdown[last:])
    return "".join(parts)


def _strip_fenced_blocks_for_context(text: str) -> str:
    return _FENCE_PLACEHOLDER_RE.sub("[code or diagram block omitted]\n", text).strip()


def _block_context(markdown: str, block_index: int) -> str:
    blocks = _list_fenced_blocks(markdown)
    block = blocks[block_index]
    before_raw = markdown[: block["start"]].split("\n")[-45:]
    after_raw = markdown[block["end"] :].split("\n")[:30]
    before = _strip_fenced_blocks_for_context("\n".join(before_raw))
    after = _strip_fenced_blocks_for_context("\n".join(after_raw))
    parts = [
        before and f"--- Context above this block ---\n{before}",
        f"--- Block to fix ---\n```{(block['lang'] or 'text')}\n{block['content']}\n```",
        after and f"--- Context below this block ---\n{after}",
    ]
    return "\n\n".join(p for p in parts if p)[:3500]


def _is_broken_code(content: str) -> bool:
    return content.strip().lower() in _BROKEN_CODE


def _mermaid_still_broken(content: str) -> bool:
    s = content.strip()
    if not s:
        return True
    if re.search(r"\s--\s+[^|>\n][^>]*\s+-->", s):
        return True
    if re.search(r"\b[A-Za-z0-9_]+\s*\(", s):
        return True
    if re.search(r"\s&\s*[A-Za-z0-9_]+\s*(-->|---)", s):
        return True
    return False


def repair_all_blocks(
    markdown: str,
    *,
    llm: LlmOptions | None = None,
    use_llm: bool = True,
) -> tuple[str, list[dict[str, Any]]]:
    """
    Fix fenced mermaid + code blocks one-by-one.
    1) Local mermaid sanitize on every mermaid block
    2) LLM (Gemma/Ollama) for blocks still broken or empty code
    """
    replacements: dict[int, str] = {}
    details: list[dict[str, Any]] = []
    blocks = _list_fenced_blocks(markdown)

    for block in blocks:
        idx = block["index"]
        lang = block["lang"]
        content = block["content"]
        new_content = content
        method: str | None = None

        if lang == "mermaid":
            sanitized = sanitize_mermaid_source(content)
            if sanitized != content:
                new_content = sanitized
                method = "sanitize"

            if _mermaid_still_broken(new_content):
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
                ctx = _block_context(markdown, idx)
                new_content = regenerate_block(
                    block_type="mermaid",
                    language="mermaid",
                    content=new_content,
                    note_context=ctx,
                    error="Mermaid diagram has invalid syntax (edge labels, stadium nodes, or special characters).",
                    mode="fix",
                    llm=llm,
                )
                new_content = sanitize_mermaid_source(new_content)
                method = f"{method}+llm" if method else "llm"

        elif lang in _CODE_LANGS and _is_broken_code(content):
            if not use_llm:
                details.append({"index": idx, "lang": lang, "method": "skipped", "status": "empty_code"})
                continue
            if not ollama_available(llm):
                details.append({"index": idx, "lang": lang, "method": "none", "status": "llm_unavailable"})
                continue
            ctx = _block_context(markdown, idx)
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

    result = _apply_block_replacements(markdown, replacements)
    return result, details
