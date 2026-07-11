"""Lecture-first notes — transcript primary; textbooks only when hits match the lecture."""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.corpus.retrieve import (
    NOTES_RAG_SOURCE_TYPES,
    corpus_available,
    hybrid_retrieve,
)
from backend.paths import NOTES_DIR
from backend.transcripts.cleanup import (
    chunk_by_words,
    clean_transcript,
    looks_like_live_captions,
    postprocess_markdown,
)
from backend.transcripts.hybrid_notes import chunk_retrieval_query
from backend.transcripts.notes_generator import (
    _effective_max_chunks,
    _limit_chunks,
    resolve_transcript_path,
)
from backend.transcripts.path_utils import build_relative_path, normalize_folder_path
from backend.transcripts.pedagogy_filter import (
    filter_hits_for_lecture,
    should_keep_transcript_span,
)

log = logging.getLogger(__name__)

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")
_QA_HINT_RE = re.compile(
    r"(?i)\b(question|vishwas|doubt|does it|will it|why (?:is|are|do|does)|what (?:is|are))\b"
)


def _topic_heading(chunk: str, *, fallback: str, index: int) -> str:
    query = chunk_retrieval_query(chunk, fallback)
    label = (query.split("—")[-1] if "—" in query else query).strip()
    label = re.sub(r"\s+", " ", label).strip(" -,:.")
    # Never invent off-lecture encyclopedia titles from empty queries
    if len(label) < 8 or label.lower() in {"lecture", "chunk", fallback.lower()}:
        # Prefer first kept tech sentence fragment
        for sent in _SENTENCE_SPLIT_RE.split(chunk):
            if should_keep_transcript_span(sent):
                label = sent.strip()[:90]
                break
        else:
            label = f"Lecture segment {index}"
    return label[:100]


def _extractive_bullets(chunk: str, *, max_bullets: int = 8) -> list[str]:
    text = re.sub(r"\s+", " ", (chunk or "").strip())
    if not text:
        return []
    sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(text) if s.strip()]
    out: list[str] = []
    budget = max_bullets
    for sent in sentences:
        if not should_keep_transcript_span(sent):
            continue
        if _QA_HINT_RE.search(sent):
            budget = max(budget, max_bullets + 2)
        words = sent.split()
        if len(words) < 5:
            continue
        bullet = sent[:320] + ("…" if len(sent) > 320 else "")
        out.append(bullet)
        if len(out) >= budget:
            break
    return out


def _cite_blocks(hits: list[dict[str, Any]], *, max_hits: int = 2, max_chars: int = 700) -> list[str]:
    blocks: list[str] = []
    for h in hits[:max_hits]:
        payload = (h.get("raw_payload") or "").strip()
        if not payload:
            continue
        cite = h.get("chunk_id") or ""
        citation = (h.get("citation") or "").strip()
        excerpt = payload[:max_chars] + ("…" if len(payload) > max_chars else "")
        lines = [f"> {line}" for line in excerpt.splitlines() if line.strip()]
        if not lines:
            continue
        header = f"**Textbook** ({citation})" if citation else "**Textbook**"
        cite_html = f" <!-- cite: {cite} -->" if cite else ""
        blocks.append(header + cite_html + "\n\n" + "\n".join(lines))
    return blocks


def assemble_notes_from_transcript(
    *,
    transcript_file: str,
    topic: str | None = None,
    folder_path: str = "",
    title: str | None = None,
    ingest_corpus: bool = False,
    on_progress: Callable[[str], None] | None = None,
    max_chunks: int = 20,
    pre_cleaned: str | None = None,
    top_k: int = 6,
) -> dict[str, Any]:
    """
    Build revision notes with the lecture as authority.

    Textbooks attach only when retrieval hits overlap the lecture query (hit gate).
    No LLM rewrite. No mermaid.
    """
    transcript_path = resolve_transcript_path(transcript_file)
    note_title = (title or topic or transcript_path.stem.replace("_", " ")).strip()
    base_topic = topic or note_title

    def progress(msg: str) -> None:
        log.info("[lecture-first] %s", msg)
        if on_progress:
            try:
                on_progress(msg)
            except Exception as exc:  # noqa: BLE001
                log.warning("on_progress failed: %s", exc)

    raw = transcript_path.read_text(encoding="utf-8")
    if pre_cleaned and pre_cleaned.strip():
        cleaned = pre_cleaned.strip()
    else:
        cleaned = clean_transcript(raw, aggressive=looks_like_live_captions(raw))
    if not cleaned.strip():
        raise ValueError("Transcript is empty after cleanup.")

    word_count = len(cleaned.split())
    progress(f"Lecture-first notes: {word_count:,} words (transcript primary)")

    chunks = chunk_by_words(cleaned, target_words=400, overlap_words=50)
    cap = _effective_max_chunks(word_count, max_chunks, fast_mode=True)
    if len(chunks) > cap:
        progress(f"Merging {len(chunks)} segments → {cap}…")
        chunks = _limit_chunks(chunks, max_chunks=cap)

    use_rag = corpus_available()
    if not use_rag:
        progress("Corpus offline — lecture-only extractive notes")

    sections: list[str] = [
        f"# {note_title.replace('_', ' ')}\n",
        "<!-- lecture_first: transcript_primary -->\n",
        "## Topics covered\n",
    ]
    topic_list: list[str] = []
    citation_ids: list[str] = []
    chunk_meta: list[dict[str, Any]] = []
    total = len(chunks)
    gated_drop = 0

    for i, chunk in enumerate(chunks, start=1):
        heading = _topic_heading(chunk, fallback=base_topic, index=i)
        # Reject encyclopedia openers that aren't in the chunk
        if re.search(r"(?i)image\s+caption", heading) and not re.search(
            r"(?i)image\s+caption|captioning", chunk
        ):
            heading = f"Lecture segment {i}"

        query = chunk_retrieval_query(chunk, base_topic) or heading
        progress(f"Segment {i}/{total}: {heading[:50]}…")

        hits: list[dict[str, Any]] = []
        if use_rag:
            raw_hits = hybrid_retrieve(
                query,
                source_types=list(NOTES_RAG_SOURCE_TYPES),
                top_k=top_k,
            )
            hits = filter_hits_for_lecture(raw_hits, query)
            gated_drop += max(0, len(raw_hits) - len(hits))
            for h in hits:
                cid = h.get("chunk_id")
                if cid and cid not in citation_ids:
                    citation_ids.append(str(cid))

        bullets = _extractive_bullets(chunk)
        if not bullets:
            # Always keep something from the chunk so we don't invent textbook topics
            excerpt = re.sub(r"\s+", " ", chunk.strip())[:240]
            if excerpt:
                bullets = [excerpt + ("…" if len(chunk.strip()) > 240 else "")]

        cites = _cite_blocks(hits) if hits else []
        topic_list.append(heading)

        body_parts = [f"## {heading}\n", "### From lecture\n"]
        body_parts.extend(f"- {b}" for b in bullets)
        body_parts.append("")
        if cites:
            body_parts.append("### From textbooks\n")
            body_parts.extend(c + "\n" for c in cites)

        sections.append("\n".join(body_parts).rstrip() + "\n")
        chunk_meta.append(
            {
                "index": i,
                "query": query,
                "hit_count": len(hits),
                "heading": heading,
            }
        )

    topics_md = "\n".join(f"- {t}" for t in topic_list) + "\n"
    sections[2] = "## Topics covered\n" + topics_md

    body = postprocess_markdown("\n".join(sections), sanitize_mermaid=False)
    # Hard ban: off-topic Image Captioning sections if lecture never said it
    if not re.search(r"(?i)image\s+caption|captioning", cleaned):
        body = _strip_heading_blocks(body, title_re=re.compile(r"(?i)image\s+caption"))

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    folder = normalize_folder_path(folder_path)
    relative = build_relative_path(folder, f"{transcript_path.stem}_{stamp}.md")
    notes_path = NOTES_DIR / relative
    notes_path.parent.mkdir(parents=True, exist_ok=True)
    header = (
        f"<!-- lecture_first: no_llm -->\n"
        f"<!-- source: {transcript_path.name} -->\n"
        f"<!-- rag_gated_drops: {gated_drop} -->\n\n"
    )
    notes_path.write_text(header + body, encoding="utf-8")

    handoff = None
    if ingest_corpus:
        try:
            from backend.corpus.handoff import ingest_lecture_handoff

            progress("Corpus handoff (optional)…")
            handoff = ingest_lecture_handoff(transcript_path=transcript_path, note_path=notes_path)
        except Exception as exc:  # noqa: BLE001
            log.warning("Handoff skipped: %s", exc)
            handoff = {"error": str(exc)}

    progress(
        f"Done — {total} segments, {len(citation_ids)} gated cites "
        f"(dropped {gated_drop} off-topic hits) → {notes_path.name}"
    )
    return {
        "mode": "lecture_first",
        "notes_path": str(notes_path),
        "filename": relative.as_posix(),
        "markdown": header + body,
        "citations": citation_ids,
        "chunk_count": total,
        "chunk_meta": chunk_meta,
        "rag_gated_drops": gated_drop,
        "corpus_handoff": handoff,
        "grounding_status": "grounded" if citation_ids else "degraded",
        "grounding_reason": None if citation_ids else "lecture_only_or_no_gated_hits",
    }


def _strip_heading_blocks(markdown: str, *, title_re: re.Pattern[str]) -> str:
    lines = markdown.splitlines()
    out: list[str] = []
    i = 0
    while i < len(lines):
        m = re.match(r"^(#{2,3})\s+(.+?)\s*$", lines[i])
        if not m:
            out.append(lines[i])
            i += 1
            continue
        level, title = m.group(1), m.group(2)
        j = i + 1
        while j < len(lines):
            hm = re.match(r"^(#{1,3})\s+", lines[j])
            if hm and len(hm.group(1)) <= len(level):
                break
            j += 1
        if title_re.search(title):
            i = j
            continue
        out.extend(lines[i:j])
        i = j
    return "\n".join(out).strip()
