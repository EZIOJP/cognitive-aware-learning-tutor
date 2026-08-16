"""Regex-based cleanup for noisy live-caption transcripts."""

from __future__ import annotations

import re

from backend.transcripts.caption_stabilize import (
    is_better_version,
    similarity_ratio,
    strip_caption_timestamp,
)
from backend.transcripts.mermaid import (  # noqa: F401
    MERMAID_GENERATION_RULES,
    aggressive_sanitize_mermaid_source,
    dedupe_repeated_mermaid_diagram,
    extract_mermaid_from_llm_output,
    is_mermaid_likely_broken,
    mermaid_lint_issues,
    sanitize_mermaid_source,
)

WHITESPACE_RE = re.compile(r"\s+")
PUNCT_ONLY_RE = re.compile(r"^[\W_]+$")
FILLER_RE = re.compile(r"\b(um+|uh+|er+|like|you know|okay so)\b", re.I)
STUTTER_RE = re.compile(r"\b(\w+)(?:\s+\1\b)+", re.I)
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
LLM_PREAMBLE_RE = re.compile(
    r"^(?:Here'?s|Sure|Certainly|Of course|Let me|Okay,?|Ok,?)\s[^\n]*\n+",
    re.I | re.M,
)
_THINK_BLOCK_RE = re.compile(r"<think(?:ing)?>[\s\S]*?</think(?:ing)?>", re.I)
_LLM_INLINE_HEADING_RE = re.compile(r"([.!?)\]:])(\s*)(#{1,6}\s+\S)")
_LLM_SCORE_INLINE_HEADING_RE = re.compile(r"(\d/5)(\s*)(#{1,6}\s+\S)")
_LLM_META_HEADING_RE = re.compile(
    r"^#{1,6}\s+(?:heading for|rules|output markdown|start with|text only|"
    r"3-5 key|preserve image|algorithm bullets|constraint checklist)",
    re.I,
)
_LLM_META_LINE_RE = re.compile(
    r"^(?:\*+\s*)?(?:Analyze the Request|Rules Check|The user wants|Confidence Score|"
    r"Drafting the content|Comparing the transcript|Given the instruction|Since the provided|"
    r"I must adhere|I will focus|I will create|Comparing the transcript content|"
    r"Plan:|Execution:|Constraint Checklist|Let me |Okay,? I |Thinking step|\d+\.\s+\*?\*?)",
    re.I,
)
OUTER_FENCE_RE = re.compile(r"^```(?:markdown)?\s*\n", re.M)
MERMAID_RE = re.compile(r"```mermaid\s*\n(.*?)```", re.DOTALL | re.I)
CODE_BLOCK_RE = re.compile(r"```[\w]*\n(.*?)```", re.DOTALL)


def normalize_segment(text: str) -> str:
    """Light cleanup for a single captured caption delta."""
    text = strip_caption_timestamp(text)
    text = WHITESPACE_RE.sub(" ", text.strip())
    text = FILLER_RE.sub(" ", text)
    text = STUTTER_RE.sub(r"\1", text)
    return WHITESPACE_RE.sub(" ", text).strip()


def looks_like_live_captions(raw: str) -> bool:
    """Heuristic: Windows Live Captions grow prefixes across many non-consecutive lines."""
    lines = [strip_caption_timestamp(ln) for ln in raw.splitlines() if ln.strip()]
    lines = [ln for ln in lines if ln]
    if len(lines) < 20:
        return False
    sample = lines[: min(500, len(lines))]
    prefix_hits = 0
    window = 48
    for i, line in enumerate(sample):
        for j in range(i + 1, min(i + window, len(sample))):
            nxt = sample[j]
            if nxt.startswith(line) and len(nxt) > len(line):
                prefix_hits += 1
                break
    return (prefix_hits / len(sample)) >= 0.12


def _token_overlap_ratio(a: str, b: str) -> float:
    ta = {w for w in a.lower().split() if w}
    tb = {w for w in b.lower().split() if w}
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / min(len(ta), len(tb))


def collapse_caption_bursts(lines: list[str], *, min_overlap: float = 0.45) -> list[str]:
    """Merge Windows Live Caption growth bursts — keep the longest line per cluster."""
    if not lines:
        return []
    out: list[str] = []
    burst: list[str] = []

    def flush_burst() -> None:
        nonlocal burst
        if burst:
            out.append(max(burst, key=len))
            burst = []

    for raw_line in lines:
        line = strip_caption_timestamp(raw_line)
        if not line or PUNCT_ONLY_RE.match(line):
            continue
        if not burst:
            burst = [line]
            continue
        anchor = max(burst, key=len)
        if line.startswith(anchor) or anchor.startswith(line):
            burst.append(line)
            continue
        if len(line) < 16 or len(anchor) < 16:
            burst.append(line)
            continue
        if _token_overlap_ratio(line, anchor) >= min_overlap:
            burst.append(line)
            continue
        flush_burst()
        burst = [line]
    flush_burst()
    return out


def collapse_live_caption_fragments(lines: list[str], *, lookahead: int = 80) -> list[str]:
    """Drop orphan Live Caption shards that are prefixes/substrings of a later line."""
    if not lines:
        return []
    out: list[str] = []
    n = len(lines)
    for i, raw_line in enumerate(lines):
        line = strip_caption_timestamp(raw_line)
        if not line or PUNCT_ONLY_RE.match(line):
            continue
        low = line.lower()
        drop = False
        for j in range(i + 1, min(i + lookahead, n)):
            other = strip_caption_timestamp(lines[j])
            if len(other) <= len(line):
                continue
            other_low = other.lower()
            if other.startswith(line):
                drop = True
                break
            if len(line) >= 8 and len(line) <= 72 and low in other_low:
                drop = True
                break
        if not drop:
            out.append(line)
    return out


def merge_similar_caption_lines(lines: list[str], *, threshold: float = 0.92) -> list[str]:
    """Keep the better of adjacent/near-duplicate sentences (SaveLC cleanup pass)."""
    if not lines:
        return []
    out: list[str] = []
    for raw in lines:
        line = strip_caption_timestamp(raw)
        if not line:
            continue
        replaced = False
        start = max(0, len(out) - 3)
        for i in range(len(out) - 1, start - 1, -1):
            if similarity_ratio(line, out[i]) < threshold:
                continue
            if is_better_version(line, out[i]):
                out[i] = line
            replaced = True
            break
        if not replaced:
            out.append(line)
    return out


def dedupe_live_caption_lines(lines: list[str]) -> list[str]:
    """Full live-caption collapse: burst merge + prefix dedup + orphan fragment removal."""
    if not lines:
        return []
    lines = [strip_caption_timestamp(ln) for ln in lines]
    lines = collapse_caption_bursts(lines)
    lines = maximal_prefix_dedup(lines)
    lines = aggressive_prefix_dedup(lines)
    lines = collapse_live_caption_fragments(lines)
    lines = merge_similar_caption_lines(lines)
    return dedupe_lines(lines)


def dedupe_lines(lines: list[str]) -> list[str]:
    """Remove exact consecutive duplicates and prefix-growing lines."""
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
    """Keep only non-prefix lines — collapses Windows Live Caption growing snapshots."""
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
    """Drop line N when line N+1 starts with line N (salvage mode for old dumps)."""
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
    """Full transcript cleanup before Ollama summarization."""
    effective_aggressive = aggressive or looks_like_live_captions(raw)
    lines = [normalize_segment(ln) for ln in raw.splitlines()]
    lines = [ln for ln in lines if ln]
    if effective_aggressive:
        lines = dedupe_live_caption_lines(lines)
    else:
        lines = dedupe_lines(lines)
    return finalize_cleaned_lines(lines)


def finalize_cleaned_lines(lines: list[str]) -> str:
    """Per-line filler/stutter cleanup, joined with newlines for readable preview."""
    cleaned: list[str] = []
    for line in lines:
        line = FILLER_RE.sub(" ", line)
        line = STUTTER_RE.sub(r"\1", line)
        line = WHITESPACE_RE.sub(" ", line).strip()
        if line:
            cleaned.append(line)
    return "\n".join(cleaned)


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


ORPHAN_SOURCE_LINE_RE = re.compile(
    r"^[\w\s.\-]+(?:\.ipynb|\.pdf|\.txt|\.md|Colab)(?:\s+[\w\s.\-]+)*$",
    re.I,
)


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


def strip_whole_response_wrapper(text: str) -> str:
    lines = text.splitlines()
    outer = re.compile(r"^```(?:markdown)?\s*$")
    if len(lines) >= 2 and outer.match(lines[0]) and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1]).strip()
    return text


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


def repair_split_code_fences(text: str) -> str:
    """Fix ```python\\n```\\n code patterns from LLM output."""
    text = re.sub(r"```(\w+)\s*\n```\s*\n", r"```\1\n", text)
    # Orphan closing fence immediately after opening with no content
    text = re.sub(r"```(\w+)\s*\n```\n", r"```\1\n", text)
    return text


def sanitize_mermaid_blocks(text: str) -> str:
    """Fix common mermaid syntax that breaks renderers (parens inside node shapes)."""
    from backend.transcripts.note_document import apply_mermaid_layout_safe

    def fix_block(match: re.Match[str]) -> str:
        body = match.group(1)
        return "```mermaid\n" + apply_mermaid_layout_safe(body) + "\n```"

    return MERMAID_RE.sub(fix_block, text)


def dedupe_h2_sections(text: str) -> str:
    """Keep the first ## section per title; drop later duplicates (cache/LLM repeats)."""
    text = text.strip()
    if not text:
        return text

    parts = re.split(r"(?=^## )", text, flags=re.MULTILINE)
    if len(parts) <= 1:
        return text

    kept: list[str] = []
    seen_h2: set[str] = set()
    head = parts[0].strip()
    if head:
        kept.append(head)

    for part in parts[1:]:
        block = part.strip()
        if not block.startswith("## "):
            continue
        title_match = re.match(r"^## (.+)$", block, re.MULTILINE)
        if not title_match:
            kept.append(block)
            continue
        key = title_match.group(1).strip().lower()
        if key in seen_h2:
            continue
        seen_h2.add(key)
        kept.append(block)

    return "\n\n".join(kept).strip()


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


def strip_llm_meta_preamble(raw: str) -> str:
    """Drop chain-of-thought / planning text before the first real markdown heading."""
    text = (raw or "").strip()
    if not text:
        return text
    text = _THINK_BLOCK_RE.sub("", text).strip()
    text = _LLM_INLINE_HEADING_RE.sub(r"\1\n\n\3", text)
    text = _LLM_SCORE_INLINE_HEADING_RE.sub(r"\1\n\n\3", text)
    for match in re.finditer(r"(?m)^#{1,6}\s+\S", text):
        line = text[match.start() :].split("\n", 1)[0].strip()
        if _LLM_META_HEADING_RE.match(line):
            continue
        return text[match.start() :].strip()
    lines = text.splitlines()
    while lines and _LLM_META_LINE_RE.match(lines[0].strip()):
        lines.pop(0)
    cleaned = "\n".join(lines).strip()
    if cleaned:
        out_lines = []
        for line in cleaned.splitlines():
            if _LLM_META_LINE_RE.match(line.strip()) and not line.strip().startswith("#"):
                continue
            out_lines.append(line)
        cleaned = "\n".join(out_lines).strip()
    return cleaned


_LOGISTICS_HEADING_RE = re.compile(
    r"(?i)(introduction\s+to\s+scalar|user\s+interface|ui\s+familiarization|"
    r"notice\s+board|note[- ]taking\s+strategy|doubt\s+resolution|"
    r"session\s+structure|conclusion\s+of\s+session|wrap[- ]?up|"
    r"chat\s+functionality|question\s+tab|platform\s+onboarding)"
)


def strip_logistics_sections(markdown: str) -> str:
    """
    Drop ##/### sections that are pure classroom/platform logistics.

    Keeps the section if it contains a cite marker or substantial technical density.
    """
    from backend.transcripts.pedagogy_filter import has_technical_substance

    text = (markdown or "").strip()
    if not text:
        return text
    lines = text.splitlines()
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r"^(#{2,3})\s+(.+?)\s*$", line)
        if not m:
            out.append(line)
            i += 1
            continue
        level, title = m.group(1), m.group(2).strip()
        j = i + 1
        body_lines: list[str] = []
        while j < len(lines):
            hm = re.match(r"^(#{1,3})\s+", lines[j])
            if hm and len(hm.group(1)) <= len(level):
                break
            body_lines.append(lines[j])
            j += 1
        body = "\n".join(body_lines)
        is_logistics = bool(_LOGISTICS_HEADING_RE.search(title))
        has_cite = "<!-- cite:" in body.lower() or "<!--cite:" in body.lower()
        if is_logistics and not has_cite and not has_technical_substance(body):
            i = j
            continue
        out.append(line)
        out.extend(body_lines)
        i = j
    return "\n".join(out).strip()


def postprocess_markdown(raw: str, *, sanitize_mermaid: bool = True) -> str:
    """Strip LLM preamble and accidental outer fences."""
    text = raw.strip()
    text = strip_llm_meta_preamble(text)
    text = LLM_PREAMBLE_RE.sub("", text).strip()
    text = strip_whole_response_wrapper(text)
    text = repair_split_code_fences(text)
    text = repair_all_fences(text)
    if sanitize_mermaid:
        text = sanitize_mermaid_blocks(text)
    text = dedupe_h2_sections(text)
    text = dedupe_notes_tail(text)
    text = strip_logistics_sections(text)
    return text.strip()


def repair_mermaid_fences(text: str) -> str:
    """Backward-compatible alias — closes all fence types."""
    return repair_all_fences(text)


def count_mermaid_blocks(text: str) -> int:
    return len(MERMAID_RE.findall(text))


def count_code_blocks(text: str) -> int:
    return len(CODE_BLOCK_RE.findall(text))
