"""Header-aware chunking with atomic code fences."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from backend.corpus.paths import DEFAULT_OVERLAP_RATIO, DEFAULT_TARGET_TOKENS

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
_FENCE_RE = re.compile(r"```(\w*)[^\S\r\n]*\r?\n([\s\S]*?)```", re.MULTILINE)
_CHAPTER_RE = re.compile(r"^(?:#+\s*)?(?:chapter|part)\s+(\d+)\b", re.I | re.MULTILINE)
_HASH_CHAPTER_RE = re.compile(r"^# (\d+)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class TextChunk:
    text: str
    breadcrumb: str
    modality_type: str
    spatial_location: int | None = None
    chunk_id: str | None = None


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _infer_modality(text: str, lang: str = "") -> str:
    lang = (lang or "").lower()
    if lang == "mermaid":
        return "mermaid_diagram"
    if lang in ("python", "py", "javascript", "js"):
        return "python_code"
    if "$$" in text or re.search(r"\\\[[\s\S]*?\\\]", text):
        return "equation"
    if re.search(r"^definition[:\s]", text.strip(), re.I):
        return "definition"
    return "narrative_text"


def _split_sections(markdown: str) -> list[tuple[str, str]]:
    """Return (breadcrumb, body) sections split on headings."""
    matches = list(_HEADING_RE.finditer(markdown))
    if not matches:
        return [("Document", markdown.strip())]

    sections: list[tuple[str, str]] = []
    trail: list[str] = []

    for i, m in enumerate(matches):
        level = len(m.group(1))
        title = m.group(2).strip()
        while len(trail) >= level:
            trail.pop()
        trail.append(title)
        breadcrumb = " > ".join(trail)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(markdown)
        body = markdown[start:end].strip()
        if body:
            sections.append((breadcrumb, body))
    return sections or [("Document", markdown.strip())]


def _extract_atomic_blocks(body: str) -> list[tuple[str, str, str]]:
    """Split body into narrative segments and fenced blocks (kept whole)."""
    parts: list[tuple[str, str, str]] = []
    last = 0
    for m in _FENCE_RE.finditer(body):
        if m.start() > last:
            pre = body[last : m.start()].strip()
            if pre:
                parts.append(("narrative", "", pre))
        lang = m.group(1) or ""
        content = m.group(2).strip()
        mod = _infer_modality(content, lang)
        fence = f"```{lang}\n{content}\n```"
        parts.append((mod, lang, fence))
        last = m.end()
    tail = body[last:].strip()
    if tail:
        parts.append(("narrative", "", tail))
    if not parts:
        parts.append(("narrative", "", body.strip()))
    return parts


def _pack_narrative(
    text: str,
    *,
    breadcrumb: str,
    target_tokens: int,
    overlap_ratio: float,
) -> list[TextChunk]:
    words = text.split()
    if not words:
        return []
    target_words = max(50, int(target_tokens * 0.75))
    overlap_words = max(1, int(target_words * overlap_ratio))
    chunks: list[TextChunk] = []
    i = 0
    part = 0
    while i < len(words):
        window = words[i : i + target_words]
        if not window:
            break
        part += 1
        chunk_text = " ".join(window)
        crumbs = breadcrumb if part == 1 else f"{breadcrumb} (cont. {part})"
        chunks.append(
            TextChunk(
                text=chunk_text,
                breadcrumb=crumbs,
                modality_type="narrative_text",
            )
        )
        if i + target_words >= len(words):
            break
        i += max(1, target_words - overlap_words)
    return chunks


def chunk_markdown(
    markdown: str,
    *,
    document_breadcrumb: str = "",
    target_tokens: int = DEFAULT_TARGET_TOKENS,
    overlap_ratio: float = DEFAULT_OVERLAP_RATIO,
    chapter: int | None = None,
) -> list[TextChunk]:
    text = markdown.strip()
    if not text:
        return []

    if chapter is not None:
        text = filter_chapter_markdown(text, chapter)
        if not text.strip():
            return []

    out: list[TextChunk] = []
    for section_crumb, body in _split_sections(text):
        crumb = f"{document_breadcrumb} > {section_crumb}".strip(" >") if document_breadcrumb else section_crumb
        for kind, lang, block in _extract_atomic_blocks(body):
            if kind != "narrative":
                out.append(
                    TextChunk(
                        text=block,
                        breadcrumb=crumb,
                        modality_type=_infer_modality(block, lang),
                    )
                )
                continue
            out.extend(
                _pack_narrative(
                    block,
                    breadcrumb=crumb,
                    target_tokens=target_tokens,
                    overlap_ratio=overlap_ratio,
                )
            )
    return [
        TextChunk(
            text=c.text,
            breadcrumb=c.breadcrumb,
            modality_type=c.modality_type,
            spatial_location=c.spatial_location,
            chunk_id=str(uuid.uuid4()),
        )
        for c in out
    ]


def _hash_chapter_starts(markdown: str) -> list[tuple[int, int]]:
    """Textbook markers like MML: `# 2` immediately followed by `## Linear Algebra`."""
    lines = markdown.splitlines(keepends=True)
    starts: list[tuple[int, int]] = []
    offset = 0
    for i, line in enumerate(lines):
        m = _HASH_CHAPTER_RE.match(line.strip())
        if m and i + 1 < len(lines) and re.match(r"^##\s+\S", lines[i + 1].strip()):
            starts.append((int(m.group(1)), offset))
        offset += len(line)
    return starts


def filter_chapter_markdown(markdown: str, chapter: int) -> str:
    """Keep markdown between chapter N and chapter N+1 headings."""
    hash_starts = _hash_chapter_starts(markdown)
    if hash_starts:
        by_num = {num: pos for num, pos in hash_starts}
        if chapter not in by_num:
            return ""
        start_idx = by_num[chapter]
        later = sorted(num for num in by_num if num > chapter)
        end_idx = by_num[later[0]] if later else len(markdown)
        return markdown[start_idx:end_idx].strip()

    matches = list(_CHAPTER_RE.finditer(markdown))
    if not matches:
        return markdown

    start_idx = None
    end_idx = len(markdown)
    for i, m in enumerate(matches):
        num = int(m.group(1))
        if num == chapter:
            start_idx = m.start()
            for m2 in matches[i + 1 :]:
                end_idx = m2.start()
                break
            break
    if start_idx is None:
        return ""
    return markdown[start_idx:end_idx].strip()
