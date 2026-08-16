"""Apps excluded from tracking and productivity stats.

Desktop tracker owns non-browser apps. Edge browsing is owned by the
SelfTracker extension (`source=extension`) — ignore msedge* here so we
don't double-count against URL/domain sessions.
"""

from __future__ import annotations

import re

# Match exe or window title (case-insensitive)
_IGNORED_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.I)
    for p in (
        r"move\s*mouse",
        r"movemouse",
        r"caffeine",  # common keep-awake tool
        r"amphetamine",  # mac keep-awake (harmless if unused on Windows)
        r"don't\s*sleep",
        r"lockapp",
        r"searchhost\.exe",
        r"steamwebhelper",
        # Edge: extension reports real sites; desktop only sees "msedge.exe"
        r"msedge\.exe",
        r"msedgewebview2\.exe",
        r"msedge_proxy\.exe",
        r"(^|[/\\])msedge(\.exe)?$",
    )
]


def is_ignored_app(exe: str, title: str = "") -> bool:
    hay = f"{exe} {title}".strip()
    if not hay:
        return False
    return any(p.search(hay) for p in _IGNORED_PATTERNS)
