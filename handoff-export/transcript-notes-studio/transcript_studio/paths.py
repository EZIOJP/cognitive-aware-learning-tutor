"""Resolve data directories — repo root via backend.paths when in monorepo."""

from __future__ import annotations

import sys
from pathlib import Path

_STUDIO_ROOT = Path(__file__).resolve().parents[1]


def _ensure_repo_on_path() -> Path:
    """Return monorepo root and ensure it is on sys.path for backend imports."""
    candidate = _STUDIO_ROOT.parent
    if (candidate / "backend" / "paths.py").is_file():
        if str(candidate) not in sys.path:
            sys.path.insert(0, str(candidate))
        return candidate
    return _STUDIO_ROOT


def repo_root() -> Path:
    _ensure_repo_on_path()
    try:
        from backend.paths import ROOT

        return ROOT
    except ImportError:
        return _STUDIO_ROOT


def transcripts_dir(override: str = "") -> Path:
    if override.strip():
        return Path(override).expanduser().resolve()
    _ensure_repo_on_path()
    try:
        from backend.paths import TRANSCRIPTS_DIR

        return TRANSCRIPTS_DIR
    except ImportError:
        return _STUDIO_ROOT / "data" / "transcripts"


def notes_dir(override: str = "") -> Path:
    if override.strip():
        return Path(override).expanduser().resolve()
    _ensure_repo_on_path()
    try:
        from backend.paths import NOTES_DIR

        return NOTES_DIR
    except ImportError:
        return _STUDIO_ROOT / "data" / "notes"


def snapshots_dir() -> Path:
    _ensure_repo_on_path()
    try:
        from backend.paths import SNAPSHOTS_DIR

        return SNAPSHOTS_DIR
    except ImportError:
        return transcripts_dir() / "snapshots"


def sessions_dir(override: str = "") -> Path:
    if override.strip():
        return Path(override).expanduser().resolve()
    return repo_root() / "data" / "sessions"
