"""Embedding-based semantic chunker — code-fence safe, fixed or percentile thresholds."""

from __future__ import annotations

import logging
import re
import time
from typing import Literal

from backend.transcripts.embedding import cosine_similarity, encode_texts, is_available

log = logging.getLogger(__name__)

FENCE_OPEN_RE = re.compile(r"^```", re.MULTILINE)
CELL_MARKER_RE = re.compile(r"^(?:In\s*\[\d*\]:|Out\s*\[\d*\]:)", re.MULTILINE | re.IGNORECASE)
SENTENCE_END_RE = re.compile(r"(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=[.!?])\s+")

ThresholdMode = Literal["fixed", "percentile"]


def _split_sentences(text: str) -> list[str]:
    paragraphs = text.splitlines(keepends=True)
    sentences: list[str] = []
    for para in paragraphs:
        stripped = para.strip()
        if not stripped:
            continue
        parts = SENTENCE_END_RE.split(stripped)
        for part in parts:
            part = part.strip()
            if part:
                sentences.append(part)
    return sentences if sentences else [text.strip()]


def _mark_code_regions(sentences: list[str], full_text: str) -> list[bool]:
    in_code_chars = bytearray(len(full_text))
    fence_depth = 0
    i = 0
    while i < len(full_text):
        if full_text[i : i + 3] == "```":
            end = full_text.find("\n", i)
            if end == -1:
                end = len(full_text)
            fence_depth = 0 if fence_depth else 1
            i = end + 1
        else:
            if fence_depth:
                in_code_chars[i] = 1
            i += 1

    for m in CELL_MARKER_RE.finditer(full_text):
        for j in range(m.start(), min(m.end() + 200, len(full_text))):
            in_code_chars[j] = 1

    result: list[bool] = []
    search_from = 0
    for sent in sentences:
        pos = full_text.find(sent, search_from)
        if pos == -1:
            result.append(False)
            continue
        result.append(bool(any(in_code_chars[pos : pos + len(sent)])))
        search_from = pos + 1
    return result


def _compute_adjacent_distances(embeddings) -> list[float]:
    distances: list[float] = []
    for i in range(len(embeddings) - 1):
        sim = cosine_similarity(embeddings[i], embeddings[i + 1])
        distances.append(1.0 - sim)
    return distances


def _find_boundaries(
    embeddings,
    in_code: list[bool],
    *,
    threshold_mode: ThresholdMode,
    threshold: float,
    percentile: float,
    max_words_per_chunk: int,
    sentences: list[str],
) -> list[int]:
    boundaries = [0]
    current_words = len(sentences[0].split())
    distances = _compute_adjacent_distances(embeddings)
    dist_threshold = threshold
    if threshold_mode == "percentile" and distances:
        import numpy as np  # noqa: PLC0415

        dist_threshold = float(np.percentile(distances, percentile))

    for i in range(len(sentences) - 1):
        word_count = len(sentences[i + 1].split())
        sim = cosine_similarity(embeddings[i], embeddings[i + 1])
        dist = 1.0 - sim
        force_split_by_size = (current_words + word_count) > max_words_per_chunk
        if threshold_mode == "percentile":
            topic_shift = dist > dist_threshold
        else:
            topic_shift = sim < threshold
        inside_code = in_code[i] or in_code[i + 1]

        if (topic_shift and not inside_code) or (force_split_by_size and not inside_code):
            boundaries.append(i + 1)
            current_words = word_count
        else:
            current_words += word_count

    return boundaries


def _assemble_chunks(sentences: list[str], boundaries: list[int]) -> list[str]:
    chunks: list[str] = []
    for idx, start in enumerate(boundaries):
        end = boundaries[idx + 1] if idx + 1 < len(boundaries) else len(sentences)
        chunk = " ".join(sentences[start:end]).strip()
        if chunk:
            chunks.append(chunk)
    return chunks


def _merge_small_chunks(chunks: list[str], min_words: int, *, max_words: int = 2500) -> list[str]:
    """Merge undersized neighbours without exceeding max_words per chunk."""
    if len(chunks) <= 1:
        return chunks

    merged: list[str] = []
    buffer = chunks[0]
    buf_words = len(buffer.split())

    for chunk in chunks[1:]:
        chunk_words = len(chunk.split())
        combined = buf_words + chunk_words
        should_merge = (buf_words < min_words or chunk_words < min_words) and combined <= max_words
        if should_merge:
            buffer = f"{buffer} {chunk}".strip()
            buf_words = combined
            continue
        merged.append(buffer)
        buffer = chunk
        buf_words = chunk_words

    merged.append(buffer)
    return merged if merged else chunks


def _enforce_max_chunk_size(chunks: list[str], *, max_words: int) -> list[str]:
    from backend.transcripts.cleanup import chunk_by_words

    out: list[str] = []
    for chunk in chunks:
        words = len(chunk.split())
        if words <= max_words:
            out.append(chunk)
            continue
        parts = chunk_by_words(chunk, target_words=max_words, overlap_words=150)
        out.extend(parts if parts else [chunk])
    return out


def semantic_chunk(
    text: str,
    *,
    model_name: str = "all-MiniLM-L6-v2",
    threshold: float = 0.45,
    threshold_mode: ThresholdMode = "fixed",
    percentile: float = 95.0,
    min_words: int = 150,
    max_words: int = 2500,
) -> list[str] | None:
    """Segment text into semantically coherent chunks. Returns None if embeddings unavailable."""
    from backend.transcripts._debug_agent_log import agent_log

    agent_log(
        location="semantic_chunker.py:semantic_chunk",
        message="chunk_start",
        data={"chars": len(text), "threshold_mode": threshold_mode},
        hypothesis_id="H1",
    )
    t0 = time.perf_counter()
    if not is_available():
        agent_log(location="semantic_chunker.py:semantic_chunk", message="embeddings_unavailable", data={}, hypothesis_id="H1")
        return None

    sentences = _split_sentences(text)
    agent_log(
        location="semantic_chunker.py:semantic_chunk",
        message="sentences_split",
        data={"sentence_count": len(sentences), "elapsed_ms": int((time.perf_counter() - t0) * 1000)},
        hypothesis_id="H1",
    )
    if len(sentences) <= 1:
        return [text.strip()] if text.strip() else None

    embeddings = encode_texts(sentences, model_name=model_name)
    agent_log(
        location="semantic_chunker.py:semantic_chunk",
        message="embeddings_done",
        data={"sentence_count": len(sentences), "elapsed_ms": int((time.perf_counter() - t0) * 1000)},
        hypothesis_id="H1",
    )
    if embeddings is None:
        return None

    in_code = _mark_code_regions(sentences, text)
    boundaries = _find_boundaries(
        embeddings,
        in_code,
        threshold_mode=threshold_mode,
        threshold=threshold,
        percentile=percentile,
        max_words_per_chunk=max_words,
        sentences=sentences,
    )
    chunks = _assemble_chunks(sentences, boundaries)
    pre_merge_count = len(chunks)
    chunks = _merge_small_chunks(chunks, min_words, max_words=max_words)
    chunks = _enforce_max_chunk_size(chunks, max_words=max_words)

    log.info(
        "Semantic chunker (%s): %d sentences → %d chunks (threshold=%.2f, percentile=%.0f)",
        threshold_mode,
        len(sentences),
        len(chunks),
        threshold,
        percentile,
    )
    agent_log(
        location="semantic_chunker.py:semantic_chunk",
        message="chunk_done",
        data={
            "pre_merge_count": pre_merge_count,
            "chunk_count": len(chunks),
            "elapsed_ms": int((time.perf_counter() - t0) * 1000),
        },
        hypothesis_id="H1",
    )
    return chunks if chunks else None
