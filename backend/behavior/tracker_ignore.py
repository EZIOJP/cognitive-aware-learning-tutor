"""Apps excluded from tracking and productivity stats (keep-awake utilities, etc.)."""

from __future__ import annotations

import re

# Match exe or window title (case-insensitive)
_IGNORED_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.I)
    for p in (
        r"move\s*mouse",
        r"movemouse",
        r"caffeine",          # common keep-awake tool
        r"amphetamine",       # mac keep-awake (harmless if unused on Windows)
        r"don't\s*sleep",
        r"lockapp",
        r"searchhost\.exe",
        r"steamwebhelper",
    )
]


def is_ignored_app(exe: str, title: str = "") -> bool:
    hay = f"{exe} {title}".strip()
    if not hay:
        return False
    return any(p.search(hay) for p in _IGNORED_PATTERNS)
