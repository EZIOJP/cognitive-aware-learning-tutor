"""Ingest lecture transcript + generated note into the searchable corpus."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from backend.corpus.ingest import ingest_note, ingest_transcript
from backend.paths import NOTES_DIR, TRANSCRIPTS_DIR

log = logging.getLogger(__name__)


def _resolve_transcript(path: Path) -> Path:
    resolved = path.resolve()
    if resolved.is_file():
        return resolved
    candidate = TRANSCRIPTS_DIR / path.name
    if candidate.is_file():
        return candidate
    raise FileNotFoundError(f"Transcript not found: {path}")


def _resolve_note(path: Path) -> Path:
    resolved = path.resolve()
    if resolved.is_file():
        return resolved
    candidate = (NOTES_DIR / path).resolve()
    if candidate.is_file() and candidate.is_relative_to(NOTES_DIR.resolve()):
        return candidate
    raise FileNotFoundError(f"Note not found: {path}")


def ingest_lecture_handoff(
    *,
    transcript_path: Path | str,
    note_path: Path | str | None = None,
) -> dict[str, Any]:
    """Index transcript and optional note markdown into hybrid RAG registry."""
    tx = _resolve_transcript(Path(transcript_path))
    out: dict[str, Any] = {"transcript_file": tx.name}

    try:
        tx_result = ingest_transcript(tx)
        out["transcript"] = tx_result
        out["transcript_chunks"] = tx_result.get("chunks_ingested", 0)
    except Exception as exc:  # noqa: BLE001
        log.warning("Transcript corpus ingest failed: %s", exc)
        out["transcript_error"] = str(exc)

    if note_path is not None:
        note = _resolve_note(Path(note_path))
        out["note_file"] = str(note.relative_to(NOTES_DIR).as_posix()) if note.is_relative_to(NOTES_DIR.resolve()) else note.name
        try:
            note_result = ingest_note(note)
            out["note"] = note_result
            out["note_chunks"] = note_result.get("chunks_ingested", 0)
        except Exception as exc:  # noqa: BLE001
            log.warning("Note corpus ingest failed: %s", exc)
            out["note_error"] = str(exc)

    return out
