"""Apps excluded from tracking and productivity stats.

Desktop/native capture ignores browser process time — SelfTracker extension owns
URL/tab sessions (`source=extension`, `app_name=msedge.exe` + active tab).

Pass `source="extension"` when aggregating so browser tab sessions are kept
and shown with friendly names (Microsoft Edge, Chrome, …).
"""

from __future__ import annotations

import re

# Match exe or window title (case-insensitive) — always drop.
_ALWAYS_IGNORED: list[re.Pattern[str]] = [
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
    )
]

# Browser processes: desktop/native capture only — extension owns tab URLs.
# Keep in sync with native IsBrowserExe + browser_labels.py (CALT original list).
_BROWSER_DESKTOP_IGNORED: list[re.Pattern[str]] = [
    re.compile(p, re.I)
    for p in (
        r"msedge\.exe",
        r"msedgewebview2\.exe",
        r"msedge_proxy\.exe",
        r"(^|[/\\])msedge(\.exe)?$",
        r"chrome\.exe",
        r"brave\.exe",
        r"firefox\.exe",
        r"opera\.exe",
        r"opera_gx\.exe",
        r"vivaldi\.exe",
        r"arc\.exe",
        r"zen\.exe",
        r"sidekick\.exe",
        r"librewolf\.exe",
        r"waterfox\.exe",
        r"floorp\.exe",
        r"thorium\.exe",
        r"chromium\.exe",
        r"iexplore\.exe",
        r"duckduckgo\.exe",
        r"avastbrowser\.exe",
    )
]


def is_ignored_app(exe: str, title: str = "", *, source: str | None = None) -> bool:
    """Return True if this app/session should be excluded.

    - Keep-awake / noise apps: always ignored.
    - Browsers: ignored for desktop/native capture (no source / desktop_tracker).
    - Browsers with ``source=extension``: kept (active tab telemetry).
    """
    hay = f"{exe} {title}".strip()
    if not hay:
        return False
    if any(p.search(hay) for p in _ALWAYS_IGNORED):
        return True
    src = (source or "").strip().lower()
    if src == "extension":
        return False
    return any(p.search(hay) for p in _BROWSER_DESKTOP_IGNORED)
