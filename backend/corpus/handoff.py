"""Corpus handoff stubs — ingest disabled after Knowledge Base removal."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def ingest_lecture_handoff(
    *,
    transcript_path: Path | str,
    note_path: Path | str | None = None,
) -> dict[str, Any]:
    return {
        "skipped": True,
        "reason": "corpus_removed",
        "transcript_file": Path(transcript_path).name,
        "transcript_chunks": 0,
        "note_chunks": 0,
    }
