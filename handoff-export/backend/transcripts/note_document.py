"""Canonical note-document model: fence indexing, markdown repair, mermaid finalize."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from backend.transcripts.cleanup import repair_all_fences, repair_split_code_fences
from backend.transcripts.mermaid import (
    aggressive_sanitize_mermaid_source,
    is_mermaid_likely_broken,
    sanitize_mermaid_source,
)

_FENCE_BLOCK_RE = re.compile(r"```(\w*)[^\S\r\n]*\r?\n([\s\S]*?)```", re.MULTILINE)
_MERMAID_RE = re.compile(r"```mermaid\s*\n(.*?)```", re.DOTALL | re.I)
_FENCE_PLACEHOLDER_RE = re.compile(r"```[\w]*[^\S\r\n]*\r?\n[\s\S]*?```", re.MULTILINE)
_STEP_HEADING_RE = re.compile(r"^Step\s+\d+:", re.I)


@dataclass(frozen=True)
class FencedBlock:
    index: int
    lang: str
    content: str
    start: int
    end: int


def _looks_like_code_line(line: str) -> bool:
    t = line.strip()
    if not t:
        return False
    if re.match(r"^(import|from|def |class |print\(|return |#|@|if |for |while |with )", t):
        return True
    if re.match(r"^[A-Za-z_]\w*\s*=", t):
        return True
    if re.match(r"^\w+\(", t):
        return True
    if re.match(r"^\w+\.\w+", t):
        return True
    return False


def repair_step_code_blocks(text: str) -> str:
    """Wrap bare code lines after Step N: headings into python fences."""
    lines = text.split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if _STEP_HEADING_RE.match(line.strip()):
            out.append(line)
            i += 1
            while i < len(lines) and not lines[i].strip():
                out.append(lines[i])
                i += 1
            code_lines: list[str] = []
            while i < len(lines):
                trimmed = lines[i].strip()
                if not trimmed:
                    break
                if (
                    _STEP_HEADING_RE.match(trimmed)
                    or re.match(r"^#{1,6}\s", trimmed)
                    or trimmed.startswith("```")
                ):
                    break
                if _looks_like_code_line(lines[i]):
                    code_lines.append(lines[i])
                    i += 1
                else:
                    break
            if code_lines:
                out.extend(["", "```python", *code_lines, "```"])
            continue
        out.append(line)
        i += 1
    return "\n".join(out)


def repair_mermaid_fences(text: str) -> str:
    """Close open ```mermaid blocks before headings or other fences."""
    lines = text.split("\n")
    out: list[str] = []
    in_mermaid = False
    for line in lines:
        trimmed = line.strip()
        if not in_mermaid and trimmed.lower().startswith("```mermaid"):
            in_mermaid = True
            out.append(line)
            continue
        if in_mermaid:
            if trimmed == "```":
                in_mermaid = False
                out.append(line)
                continue
            if re.match(r"^#{1,6}\s", line):
                out.append("```")
                in_mermaid = False
                out.append(line)
                continue
            if re.match(r"^```\w", trimmed) and not trimmed.lower().startswith("```mermaid"):
                out.append("```")
                in_mermaid = False
                out.append(line)
                continue
        out.append(line)
    if in_mermaid:
        out.append("```")
    return "\n".join(out)


def prepare_note_markdown(raw: str) -> str:
    """Viewer repair pipeline — mirrors src/features/study-notes/noteDocument.ts."""
    out = raw
    out = repair_split_code_fences(out)
    out = repair_all_fences(out)
    out = repair_step_code_blocks(out)
    out = repair_mermaid_fences(out)
    return out


def list_fenced_blocks(markdown: str) -> list[FencedBlock]:
    blocks: list[FencedBlock] = []
    for m in _FENCE_BLOCK_RE.finditer(markdown):
        blocks.append(
            FencedBlock(
                index=len(blocks),
                lang=(m.group(1) or "text").lower(),
                content=m.group(2).rstrip("\n"),
                start=m.start(),
                end=m.end(),
            )
        )
    return blocks


def _format_fence(lang: str, body: str) -> str:
    lang = lang.strip()
    if lang and lang != "text":
        return f"```{lang}\n{body.strip()}\n```"
    return f"```\n{body.strip()}\n```"


def replace_fenced_block(markdown: str, block_index: int, new_content: str) -> str:
    blocks = list_fenced_blocks(markdown)
    if block_index < 0 or block_index >= len(blocks):
        n = len(blocks)
        raise ValueError(
            f"Could not save block {block_index}: note has {n} fenced block{'s' if n != 1 else ''}."
        )
    block = blocks[block_index]
    fence = _format_fence(block.lang, new_content)
    return markdown[: block.start] + fence + markdown[block.end :]


def apply_block_update(markdown: str, block_index: int, new_content: str, *, lang: str | None = None) -> str:
    blocks = list_fenced_blocks(markdown)
    if block_index < 0 or block_index >= len(blocks):
        raise ValueError(f"Block index {block_index} out of range")
    block = blocks[block_index]
    body = new_content
    if (lang or block.lang) == "mermaid":
        body = apply_mermaid_layout_safe(new_content)
    return replace_fenced_block(markdown, block_index, body)


def apply_mermaid_layout_safe(body: str) -> str:
    """sanitize + aggressive layout pass (contract mirror of frontend layoutSafeMermaidSource)."""
    return aggressive_sanitize_mermaid_source(sanitize_mermaid_source(body)).strip()


def layout_safe_mermaid_blocks(text: str) -> str:
    def fix_block(match: re.Match[str]) -> str:
        body = apply_mermaid_layout_safe(match.group(1))
        return f"```mermaid\n{body}\n```"

    return _MERMAID_RE.sub(fix_block, text)


def finalize_note_markdown(md: str) -> str:
    """Prepare + layout-safe all mermaid fences before persisting to disk."""
    return layout_safe_mermaid_blocks(prepare_note_markdown(md))


def apply_block_replacements(markdown: str, replacements: dict[int, str]) -> str:
    if not replacements:
        return markdown
    blocks = list_fenced_blocks(markdown)
    parts: list[str] = []
    last = 0
    for block in blocks:
        parts.append(markdown[last : block.start])
        body = replacements.get(block.index, block.content)
        parts.append(_format_fence(block.lang, body))
        last = block.end
    parts.append(markdown[last:])
    return "".join(parts)


def strip_fenced_blocks_for_context(text: str) -> str:
    return _FENCE_PLACEHOLDER_RE.sub("[code or diagram block omitted]\n", text).strip()


def block_surrounding_context(markdown: str, block_index: int, *, block_content: str | None = None) -> str:
    blocks = list_fenced_blocks(markdown)
    if block_index < 0 or block_index >= len(blocks):
        return markdown[:3500]
    block = blocks[block_index]
    body = block_content if block_content is not None else block.content
    before_raw = markdown[: block.start].split("\n")[-45:]
    after_raw = markdown[block.end :].split("\n")[:30]
    before = strip_fenced_blocks_for_context("\n".join(before_raw))
    after = strip_fenced_blocks_for_context("\n".join(after_raw))
    parts = [
        before and f"--- Context above this block ---\n{before}",
        f"--- Block to fix ---\n```{(block.lang or 'text')}\n{body}\n```",
        after and f"--- Context below this block ---\n{after}",
    ]
    return "\n\n".join(p for p in parts if p)[:3500]


def mermaid_still_broken(content: str) -> bool:
    return is_mermaid_likely_broken(sanitize_mermaid_source(content))


def fenced_blocks_as_dicts(markdown: str) -> list[dict[str, Any]]:
    return [
        {
            "index": b.index,
            "lang": b.lang,
            "content": b.content,
            "start": b.start,
            "end": b.end,
        }
        for b in list_fenced_blocks(markdown)
    ]
