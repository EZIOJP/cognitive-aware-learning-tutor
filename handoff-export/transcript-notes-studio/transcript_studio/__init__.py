"""Transcript Notes Studio — standalone parser + summarizer."""

from __future__ import annotations

import sys
from pathlib import Path

__version__ = "1.0.0"

_STUDIO_ROOT = Path(__file__).resolve().parents[1]
_REPO_ROOT = _STUDIO_ROOT.parent
if (_REPO_ROOT / "backend").is_dir() and str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
