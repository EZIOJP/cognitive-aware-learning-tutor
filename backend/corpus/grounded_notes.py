"""Grounded-notes stubs — corpus RAG removed; callers should use Lecture Notes legacy path."""

from __future__ import annotations

from typing import Any


def generate_grounded_notes(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
    raise RuntimeError(
        "Corpus RAG was removed. Use Lecture Notes transcript generation (non-grounded path)."
    )


def generate_grounded_notes_single_shot(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
    raise RuntimeError(
        "Corpus RAG was removed. Use Lecture Notes transcript generation (non-grounded path)."
    )


def generate_grounded_notes_smart(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
    raise RuntimeError(
        "Corpus RAG was removed. Use Lecture Notes transcript generation (non-grounded path)."
    )
