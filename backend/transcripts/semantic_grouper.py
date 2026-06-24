"""Embed transcript segments and cluster by topic before summarization.

Superseded by transcript_studio.semantic_grouping + topic_pipeline.merge_similar_groups.
Kept for legacy tests only; notes_generator no longer imports this module.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass

from backend.transcripts.cleanup import chunk_by_words, split_sentences
from backend.transcripts.embedding import cosine_similarity, encode_texts, mean_vector

# Avoid tokenizer subprocess noise on Windows during embedding grouping
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

log = logging.getLogger(__name__)

SENTENCE_END_RE = re.compile(r"(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=[.!?])\s+")


@dataclass
class TopicGroup:
    """One semantic topic cluster from the transcript."""

    segment_indices: list[int]
    text: str
    first_index: int
    label: str = ""


def _pack_segments(sentences: list[str], *, target_words: int) -> list[str]:
    segments: list[str] = []
    current: list[str] = []
    current_words = 0

    for sentence in sentences:
        words = len(sentence.split())
        if current_words + words > target_words and current:
            segments.append(" ".join(current))
            current = [sentence]
            current_words = words
        else:
            current.append(sentence)
            current_words += words

    if current:
        segments.append(" ".join(current))
    return segments


def segment_transcript(text: str, *, segment_words: int = 120) -> list[str]:
    sentences = split_sentences(text)
    if not sentences:
        stripped = text.strip()
        return [stripped] if stripped else []
    return _pack_segments(sentences, target_words=segment_words)


def _union_find_clusters(n: int, pairs: list[tuple[int, int]]) -> list[list[int]]:
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[rj] = ri

    for i, j in pairs:
        union(i, j)

    buckets: dict[int, list[int]] = {}
    for i in range(n):
        buckets.setdefault(find(i), []).append(i)
    return [sorted(indices) for indices in buckets.values()]


def _split_oversized_cluster(indices: list[int], segments: list[str], *, max_words: int) -> list[list[int]]:
    total = sum(len(segments[i].split()) for i in indices)
    if total <= max_words or len(indices) <= 1:
        return [indices]

    parts: list[list[int]] = []
    current: list[int] = []
    current_words = 0
    for idx in indices:
        words = len(segments[idx].split())
        if current_words + words > max_words and current:
            parts.append(current)
            current = [idx]
            current_words = words
        else:
            current.append(idx)
            current_words += words
    if current:
        parts.append(current)
    return parts


def _label_for_group(segments: list[str], indices: list[int]) -> str:
    first = segments[indices[0]].strip()
    words = first.split()[:8]
    label = " ".join(words)
    if len(label) > 60:
        label = label[:57] + "…"
    return label


def group_transcript(
    cleaned: str,
    *,
    segment_words: int = 120,
    cluster_threshold: float = 0.72,
    max_words_per_group: int = 4000,
    model_name: str = "all-MiniLM-L6-v2",
) -> list[TopicGroup] | None:
    """Cluster transcript segments by embedding similarity. Returns None if embeddings unavailable."""
    segments = segment_transcript(cleaned, segment_words=segment_words)
    if not segments:
        return None
    if len(segments) == 1:
        return [TopicGroup(segment_indices=[0], text=segments[0], first_index=0, label=_label_for_group(segments, [0]))]

    embeddings = encode_texts(segments, model_name=model_name)
    if embeddings is None:
        return None

    pairs: list[tuple[int, int]] = []
    n = len(segments)
    for i in range(n):
        for j in range(i + 1, n):
            if cosine_similarity(embeddings[i], embeddings[j]) >= cluster_threshold:
                pairs.append((i, j))

    raw_clusters = _union_find_clusters(n, pairs)
    split_clusters: list[list[int]] = []
    for cluster in raw_clusters:
        split_clusters.extend(_split_oversized_cluster(cluster, segments, max_words=max_words_per_group))

    groups: list[TopicGroup] = []
    for indices in split_clusters:
        ordered = sorted(indices)
        text = "\n\n".join(segments[i] for i in ordered).strip()
        groups.append(
            TopicGroup(
                segment_indices=ordered,
                text=text,
                first_index=ordered[0],
                label=_label_for_group(segments, ordered),
            )
        )

    groups.sort(key=lambda g: g.first_index)
    log.info(
        "Semantic grouper: %d segments → %d topic groups (threshold=%.2f)",
        len(segments),
        len(groups),
        cluster_threshold,
    )
    return groups


def groups_from_word_chunks(cleaned: str, *, target_words: int = 2000) -> list[TopicGroup]:
    """Fallback when embeddings are unavailable."""
    chunks = chunk_by_words(cleaned, target_words=target_words, overlap_words=200) or [cleaned]
    groups: list[TopicGroup] = []
    for i, chunk in enumerate(chunks):
        groups.append(TopicGroup(segment_indices=[i], text=chunk, first_index=i, label=f"Section {i + 1}"))
    return groups


def split_reference_chunks(reference: str, *, chunk_words: int = 400) -> list[str]:
    if not reference.strip():
        return []
    parts = re.split(r"\n---+\n|\n### Reference:", reference)
    chunks: list[str] = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        for window in _pack_segments(split_sentences(part) or [part], target_words=chunk_words):
            if window.strip():
                chunks.append(window.strip())
    return chunks if chunks else [reference[:12000]]


def match_reference_chunk(
    group_text: str,
    reference_chunks: list[str],
    *,
    model_name: str = "all-MiniLM-L6-v2",
) -> str:
    if not reference_chunks:
        return ""
    if len(reference_chunks) == 1:
        return reference_chunks[0]

    vectors = encode_texts([group_text, *reference_chunks], model_name=model_name)
    if vectors is None or len(vectors) < 2:
        return reference_chunks[0]

    group_vec = vectors[0]
    best_idx = 0
    best_score = -1.0
    for i, ref_vec in enumerate(vectors[1:], start=0):
        score = cosine_similarity(group_vec, ref_vec)
        if score > best_score:
            best_score = score
            best_idx = i
    return reference_chunks[best_idx]
