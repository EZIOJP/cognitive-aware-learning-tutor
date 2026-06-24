"""Regex-based cleanup for noisy live-caption transcripts."""

from __future__ import annotations

import re

WHITESPACE_RE = re.compile(r"\s+")
FILLER_RE = re.compile(r"\b(um+|uh+|er+|like|you know|okay so)\b", re.I)
STUTTER_RE = re.compile(r"\b(\w+)(?:\s+\1\b)+", re.I)
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
LLM_PREAMBLE_RE = re.compile(r"^(?:Here'?s|Sure|Certainly|Of course)[^\n]*\n+", re.I | re.M)
OUTER_FENCE_LINE_RE = re.compile(r"^```(?:markdown)?\s*$")
MERMAID_RE = re.compile(r"```mermaid\s*\n(.*?)```", re.DOTALL | re.I)
CODE_BLOCK_RE = re.compile(r"```[\w]*\n(.*?)```", re.DOTALL)
ORPHAN_SOURCE_LINE_RE = re.compile(
    r"^[\w\s.\-]+(?:\.ipynb|\.pdf|\.txt|\.md|Colab)(?:\s+[\w\s.\-]+)*$",
    re.I,
)


def normalize_segment(text: str) -> str:
    text = WHITESPACE_RE.sub(" ", text.strip())
    text = FILLER_RE.sub(" ", text)
    text = STUTTER_RE.sub(r"\1", text)
    return WHITESPACE_RE.sub(" ", text).strip()


def dedupe_lines(lines: list[str]) -> list[str]:
    if not lines:
        return []
    out: list[str] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if out and out[-1] == line:
            continue
        if out and line.startswith(out[-1]) and len(line) > len(out[-1]):
            out[-1] = line
            continue
        out.append(line)
    return out


def maximal_prefix_dedup(lines: list[str]) -> list[str]:
    out: list[str] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        out = [x for x in out if not (line.startswith(x) and len(line) > len(x))]
        if any(line.startswith(x) and len(x) >= len(line) for x in out):
            continue
        out.append(line)
    return out


def aggressive_prefix_dedup(lines: list[str]) -> list[str]:
    if len(lines) < 2:
        return lines
    out: list[str] = []
    i = 0
    while i < len(lines):
        current = lines[i].strip()
        if not current:
            i += 1
            continue
        if i + 1 < len(lines):
            nxt = lines[i + 1].strip()
            if nxt.startswith(current) and len(nxt) > len(current):
                i += 1
                continue
        out.append(current)
        i += 1
    return dedupe_lines(out)


def clean_transcript(raw: str, *, aggressive: bool = False) -> str:
    lines = [normalize_segment(ln) for ln in raw.splitlines()]
    lines = [ln for ln in lines if ln]
    if aggressive:
        lines = maximal_prefix_dedup(lines)
    else:
        lines = dedupe_lines(lines)
    text = " ".join(lines)
    text = FILLER_RE.sub(" ", text)
    text = STUTTER_RE.sub(r"\1", text)
    return WHITESPACE_RE.sub(" ", text).strip()


def split_sentences(text: str) -> list[str]:
    parts = SENTENCE_SPLIT_RE.split(text.strip())
    return [p.strip() for p in parts if p.strip()]


def chunk_by_words(text: str, target_words: int = 2500, overlap_words: int = 200) -> list[str]:
    sentences = split_sentences(text)
    if not sentences:
        return []
    chunks: list[str] = []
    current: list[str] = []
    current_words = 0

    for sentence in sentences:
        words = len(sentence.split())
        if current_words + words > target_words and current:
            chunks.append(" ".join(current))
            overlap: list[str] = []
            overlap_count = 0
            for s in reversed(current):
                overlap.insert(0, s)
                overlap_count += len(s.split())
                if overlap_count >= overlap_words:
                    break
            current = overlap
            current_words = sum(len(s.split()) for s in current)
        current.append(sentence)
        current_words += words

    if current:
        chunks.append(" ".join(current))
    return chunks


def strip_whole_response_wrapper(text: str) -> str:
    """Strip a fence only when it wraps the entire response (first and last line)."""
    lines = text.splitlines()
    if (
        len(lines) >= 2
        and OUTER_FENCE_LINE_RE.match(lines[0])
        and lines[-1].strip() == "```"
    ):
        return "\n".join(lines[1:-1]).strip()
    return text


def repair_all_fences(text: str) -> str:
    """Close orphaned ``` fences (any language), not just mermaid."""
    lines = text.splitlines()
    out: list[str] = []
    in_fence = False

    for line in lines:
        stripped = line.strip()

        if not in_fence and stripped.startswith("```"):
            in_fence = True
            out.append(line)
            continue

        if in_fence and stripped == "```":
            in_fence = False
            out.append(line)
            continue

        if in_fence and (stripped.startswith("```") or re.match(r"^#{1,6}\s", line)):
            out.append("```")
            in_fence = False

        out.append(line)

    if in_fence:
        out.append("```")

    return "\n".join(out)


def trim_incomplete_tail(text: str) -> str:
    lines = text.splitlines()
    while lines:
        last = lines[-1].strip()
        if not last:
            lines.pop()
            continue
        if len(last) < 5 and not last.endswith((".", "!", "?", "`", ")", "]")):
            lines.pop()
            continue
        break
    return "\n".join(lines).strip()


def dedupe_notes_tail(text: str) -> str:
    """Remove trailing duplicate sections and orphan source filename lines."""
    lines = text.splitlines()
    while lines and ORPHAN_SOURCE_LINE_RE.match(lines[-1].strip()):
        lines.pop()
    text = "\n".join(lines).strip()

    h2_positions: list[tuple[str, int]] = []
    for match in re.finditer(r"^## (.+)$", text, re.MULTILINE):
        h2_positions.append((match.group(1).strip().lower(), match.start()))

    seen: dict[str, int] = {}
    cut: int | None = None
    for title, pos in h2_positions:
        if title in seen and pos > len(text) * 0.5:
            cut = pos
            break
        seen[title] = pos

    if cut is not None:
        text = text[:cut].rstrip()
    return trim_incomplete_tail(text)


def postprocess_markdown(raw: str) -> str:
    text = raw.strip()
    text = LLM_PREAMBLE_RE.sub("", text).strip()
    text = strip_whole_response_wrapper(text)
    text = repair_all_fences(text)
    text = dedupe_notes_tail(text)
    return text.strip()


def count_mermaid_blocks(text: str) -> int:
    return len(MERMAID_RE.findall(text))


def count_code_blocks(text: str) -> int:
    return len(CODE_BLOCK_RE.findall(text))
