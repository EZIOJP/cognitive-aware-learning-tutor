"""Embedding-based semantic chunker for lecture transcripts.

Replaces fixed-size word-count chunking with cosine-similarity boundary detection.
Code blocks (markdown fences and Colab In/Out markers) are never split across chunks.

Dependencies: sentence-transformers (CPU-only; does not require GPU).
Falls back gracefully to word-count chunking when the model is unavailable.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------
FENCE_OPEN_RE = re.compile(r"^```", re.MULTILINE)
FENCE_CLOSE_RE = re.compile(r"^```\s*$", re.MULTILINE)
# Colab / Jupyter execution markers (reuses same pattern as notebook_pdf.py)
CELL_MARKER_RE = re.compile(r"^(?:In\s*\[\d*\]:|Out\s*\[\d*\]:)", re.MULTILINE | re.IGNORECASE)
# Sentence boundary: end of sentence followed by whitespace (avoids splitting abbreviations)
SENTENCE_END_RE = re.compile(r"(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=[.!?])\s+")

_EMBEDDING_MODEL: object = None  # cached singleton


def _load_model(model_name: str = "all-MiniLM-L6-v2") -> object | None:
    """Load sentence-transformer model once; return None if unavailable."""
    global _EMBEDDING_MODEL
    if _EMBEDDING_MODEL is not None:
        return _EMBEDDING_MODEL
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore

        log.info("Loading embedding model %s on CPU…", model_name)
        _EMBEDDING_MODEL = SentenceTransformer(model_name, device="cpu")
        log.info("Embedding model loaded.")
        return _EMBEDDING_MODEL
    except ImportError:
        log.warning(
            "sentence-transformers not installed. "
            "Install it with: pip install sentence-transformers\n"
            "Falling back to word-count chunking."
        )
        return None
    except Exception as exc:  # noqa: BLE001
        log.warning("Could not load embedding model: %s. Falling back to word-count chunking.", exc)
        return None


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences while preserving paragraph structure."""
    # First split on newlines to keep paragraph markers
    paragraphs = text.splitlines(keepends=True)
    sentences: list[str] = []
    for para in paragraphs:
        stripped = para.strip()
        if not stripped:
            continue
        # Further split prose paragraphs on sentence boundaries
        parts = SENTENCE_END_RE.split(stripped)
        for part in parts:
            part = part.strip()
            if part:
                sentences.append(part)
    return sentences if sentences else [text.strip()]


def _mark_code_regions(sentences: list[str], full_text: str) -> list[bool]:
    """Return a bool list: True if a sentence is inside a code fence or cell marker."""
    # Build character-level code mask from the full text
    in_code_chars = bytearray(len(full_text))
    fence_depth = 0
    i = 0
    while i < len(full_text):
        if full_text[i:i+3] == "```":
            # Find end of fence line
            end = full_text.find("\n", i)
            if end == -1:
                end = len(full_text)
            if fence_depth == 0:
                fence_depth = 1
            else:
                fence_depth = 0
                # Mark closing fence itself
                for j in range(i, min(end + 1, len(full_text))):
                    in_code_chars[j] = 1
            i = end + 1
        else:
            if fence_depth:
                in_code_chars[i] = 1
            i += 1

    # Also mark Colab cell markers
    for m in CELL_MARKER_RE.finditer(full_text):
        for j in range(m.start(), min(m.end() + 200, len(full_text))):
            in_code_chars[j] = 1

    # Map each sentence to its char position and check the mask
    result: list[bool] = []
    search_from = 0
    for sent in sentences:
        pos = full_text.find(sent, search_from)
        if pos == -1:
            result.append(False)
            continue
        # Sentence is in code if ANY char of it is in a code region
        is_code = any(in_code_chars[pos: pos + len(sent)])
        result.append(bool(is_code))
        search_from = pos + 1

    return result


def _cosine_similarity(a: "np.ndarray", b: "np.ndarray") -> float:
    import numpy as np  # noqa: PLC0415

    norm_a = float(np.linalg.norm(a))
    norm_b = float(np.linalg.norm(b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def _find_boundaries(
    embeddings: "np.ndarray",
    in_code: list[bool],
    threshold: float,
    max_words_per_chunk: int,
    sentences: list[str],
) -> list[int]:
    """Return indices of sentences where a new chunk should start (always includes 0)."""
    boundaries = [0]
    current_words = len(sentences[0].split())

    for i in range(len(sentences) - 1):
        word_count = len(sentences[i + 1].split())
        sim = _cosine_similarity(embeddings[i], embeddings[i + 1])
        force_split_by_size = (current_words + word_count) > max_words_per_chunk
        topic_shift = sim < threshold
        inside_code = in_code[i] or in_code[i + 1]

        if (topic_shift and not inside_code) or (force_split_by_size and not inside_code):
            boundaries.append(i + 1)
            current_words = word_count
        else:
            current_words += word_count

    return boundaries


def _assemble_chunks(sentences: list[str], boundaries: list[int]) -> list[str]:
    """Group sentences into chunks based on boundary indices."""
    chunks: list[str] = []
    for idx, start in enumerate(boundaries):
        end = boundaries[idx + 1] if idx + 1 < len(boundaries) else len(sentences)
        chunk = " ".join(sentences[start:end]).strip()
        if chunk:
            chunks.append(chunk)
    return chunks


def _merge_small_chunks(chunks: list[str], min_words: int) -> list[str]:
    """Merge chunks that are smaller than min_words with their nearest neighbour."""
    if len(chunks) <= 1:
        return chunks
    merged: list[str] = []
    i = 0
    while i < len(chunks):
        chunk = chunks[i]
        word_count = len(chunk.split())
        if word_count < min_words and merged:
            # Append to previous chunk
            merged[-1] = merged[-1] + " " + chunk
        elif word_count < min_words and i + 1 < len(chunks):
            # Prepend to next chunk
            chunks[i + 1] = chunk + " " + chunks[i + 1]
        else:
            merged.append(chunk)
        i += 1
    return merged if merged else chunks


def semantic_chunk(
    text: str,
    *,
    model_name: str = "all-MiniLM-L6-v2",
    threshold: float = 0.45,
    min_words: int = 150,
    max_words: int = 2500,
) -> list[str] | None:
    """Segment text into semantically coherent chunks.

    Returns None if sentence-transformers is unavailable (caller should fall
    back to chunk_by_words).

    Args:
        text: Cleaned transcript or note text.
        model_name: Sentence-transformer model to use (CPU only).
        threshold: Cosine similarity below which a boundary is inserted (0–1).
        min_words: Chunks smaller than this are merged with a neighbour.
        max_words: Hard upper limit per chunk; overrides similarity if needed.

    Returns:
        List of chunk strings, or None on failure.
    """
    model = _load_model(model_name)
    if model is None:
        return None

    sentences = _split_sentences(text)
    if len(sentences) <= 1:
        return [text.strip()] if text.strip() else None

    try:
        import numpy as np  # noqa: PLC0415

        embeddings: np.ndarray = model.encode(  # type: ignore[union-attr]
            sentences,
            convert_to_numpy=True,
            show_progress_bar=False,
            batch_size=64,
            device="cpu",
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("Embedding failed: %s. Falling back to word-count chunking.", exc)
        return None

    in_code = _mark_code_regions(sentences, text)
    boundaries = _find_boundaries(embeddings, in_code, threshold, max_words, sentences)
    chunks = _assemble_chunks(sentences, boundaries)
    chunks = _merge_small_chunks(chunks, min_words)

    log.info(
        "Semantic chunker: %d sentences → %d chunks (threshold=%.2f)",
        len(sentences),
        len(chunks),
        threshold,
    )
    return chunks if chunks else None


def is_available() -> bool:
    """Return True if sentence-transformers is installed and model can load."""
    return _load_model() is not None
