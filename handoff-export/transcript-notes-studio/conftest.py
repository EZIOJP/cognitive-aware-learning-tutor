"""Pytest bootstrap — repo root on sys.path for backend imports."""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_STUDIO_ROOT = Path(__file__).resolve().parent

for path in (_REPO_ROOT, _STUDIO_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
