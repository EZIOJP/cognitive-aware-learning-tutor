"""Shared notes/questions mtime stamps for cache coherence."""

from __future__ import annotations

import time
from pathlib import Path

from backend import paths

_notes_stamp: float = 0.0
_questions_stamp: float = 0.0


def _dir_mtime(root: Path) -> float:
    if not root.is_dir():
        return 0.0
    best = 0.0
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        try:
            best = max(best, p.stat().st_mtime)
        except OSError:
            continue
    return best


def notes_stamp() -> float:
    global _notes_stamp
    if _notes_stamp == 0.0:
        _notes_stamp = _dir_mtime(paths.NOTES_DIR)
    return _notes_stamp


def questions_stamp() -> float:
    global _questions_stamp
    if _questions_stamp == 0.0:
        _questions_stamp = _dir_mtime(paths.QUESTIONS_DIR)
    return _questions_stamp


def bump_notes() -> float:
    global _notes_stamp
    _notes_stamp = time.time()
    return _notes_stamp


def bump_questions() -> float:
    global _questions_stamp
    _questions_stamp = time.time()
    return _questions_stamp
