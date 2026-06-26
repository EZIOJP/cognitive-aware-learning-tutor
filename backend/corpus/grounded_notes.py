"""Corpus-grounded notes generation."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.core.ollama_client import LlmOptions, ollama_available, ollama_generate
from backend.corpus.retrieve import corpus_available, format_hits_for_prompt, hybrid_retrieve
from backend.paths import NOTES_DIR
from backend.transcripts.note_document import finalize_note_markdown
from backend.transcripts.notes_generator import generate_notes_from_file, resolve_transcript_path
from backend.transcripts.path_utils import build_relative_path, normalize_folder_path


def _write_note_file(
    markdown: str,
    *,
    title: str,
    folder_path: str = "",
) -> Path:
    body = finalize_note_markdown(markdown.strip())
    folder = normalize_folder_path(folder_path)
    if folder:
        (NOTES_DIR / folder).mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe_title = "".join(c if c.isalnum() or c in "-_" else "_" for c in title)[:60].strip()
    safe_title = safe_title.replace(" ", "_") or "lecture"
    relative = build_relative_path(folder, f"{safe_title}_{stamp}.md")
    path = NOTES_DIR / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def generate_grounded_notes(
    *,
    transcript_file: str,
    topic: str = "",
    folder_path: str = "",
    title: str | None = None,
    llm: LlmOptions | None = None,
    ingest_corpus: bool = True,
) -> dict[str, Any]:
    transcript_path = resolve_transcript_path(transcript_file)
    note_title = (title or topic or transcript_path.stem.replace("_", " ")).strip()

    if not corpus_available():
        notes_path, content = generate_notes_from_file(transcript_path, title=note_title, folder_path=folder_path)
        handoff = None
        if ingest_corpus:
            from backend.corpus.handoff import ingest_lecture_handoff

            handoff = ingest_lecture_handoff(transcript_path=transcript_path, note_path=notes_path)
        rel = notes_path.relative_to(NOTES_DIR).as_posix()
        return {
            "mode": "legacy",
            "filename": rel,
            "notes_path": str(notes_path),
            "markdown": content,
            "corpus_handoff": handoff,
        }

    query = topic or transcript_path.stem.replace("_", " ")
    hits = hybrid_retrieve(query, subject_tags=["lecture", "linear_algebra"], top_k=8)
    context = format_hits_for_prompt(hits, max_chars=14000)

    if not ollama_available(llm):
        notes_path, content = generate_notes_from_file(transcript_path, title=note_title, folder_path=folder_path)
        handoff = None
        if ingest_corpus:
            from backend.corpus.handoff import ingest_lecture_handoff

            handoff = ingest_lecture_handoff(transcript_path=transcript_path, note_path=notes_path)
        rel = notes_path.relative_to(NOTES_DIR).as_posix()
        return {
            "mode": "legacy_llm_off",
            "filename": rel,
            "notes_path": str(notes_path),
            "markdown": content,
            "chunk_count": len(hits),
            "corpus_handoff": handoff,
        }

    raw = transcript_path.read_text(encoding="utf-8")[:12000]

    prompt = f"""Write structured lecture notes in markdown from the transcript below.
Use ONLY facts supported by the REFERENCE CHUNKS. Add <!-- cite: chunk_id --> after each major section heading.

REFERENCE CHUNKS:
{context}

TRANSCRIPT:
{raw}

Output markdown only."""

    md = ollama_generate(prompt, timeout=180.0, llm=llm)
    if not md or not md.strip():
        notes_path, content = generate_notes_from_file(transcript_path, title=note_title, folder_path=folder_path)
        handoff = None
        if ingest_corpus:
            from backend.corpus.handoff import ingest_lecture_handoff

            handoff = ingest_lecture_handoff(transcript_path=transcript_path, note_path=notes_path)
        rel = notes_path.relative_to(NOTES_DIR).as_posix()
        return {
            "mode": "legacy_fallback",
            "filename": rel,
            "notes_path": str(notes_path),
            "markdown": content,
            "corpus_handoff": handoff,
        }

    notes_path = _write_note_file(md, title=note_title, folder_path=folder_path)
    handoff = None
    if ingest_corpus:
        from backend.corpus.handoff import ingest_lecture_handoff

        handoff = ingest_lecture_handoff(transcript_path=transcript_path, note_path=notes_path)
    rel = notes_path.relative_to(NOTES_DIR).as_posix()
    return {
        "mode": "grounded",
        "filename": rel,
        "notes_path": str(notes_path),
        "markdown": finalize_note_markdown(md.strip()),
        "chunk_count": len(hits),
        "citations": [h.get("chunk_id") for h in hits],
        "corpus_handoff": handoff,
    }
