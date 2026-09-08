"""Browser exe display names + domain extraction for tracked sessions."""

from __future__ import annotations

import re

# Canonical exe → UI label (broad browser coverage — CALT original list, not CT).
_BROWSER_LABELS: dict[str, str] = {
    "msedge.exe": "Microsoft Edge",
    "msedgewebview2.exe": "Microsoft Edge",
    "chrome.exe": "Google Chrome",
    "brave.exe": "Brave",
    "firefox.exe": "Firefox",
    "opera.exe": "Opera",
    "opera_gx.exe": "Opera GX",
    "vivaldi.exe": "Vivaldi",
    "arc.exe": "Arc",
    "zen.exe": "Zen",
    "sidekick.exe": "Sidekick",
    "librewolf.exe": "LibreWolf",
    "waterfox.exe": "Waterfox",
    "floorp.exe": "Floorp",
    "thorium.exe": "Thorium",
    "chromium.exe": "Chromium",
    "iexplore.exe": "Internet Explorer",
    "duckduckgo.exe": "DuckDuckGo",
    "avastbrowser.exe": "Avast Secure Browser",
}

_DOMAIN_IN_TITLE = re.compile(
    r"(?:·|—|-)\s*([a-z0-9][a-z0-9.-]+\.[a-z]{2,})\s*$",
    re.I,
)
_DOMAIN_ANYWHERE = re.compile(
    r"(?:·|—|-)\s*([a-z0-9][a-z0-9.-]+\.[a-z]{2,})(?:\s|$)",
    re.I,
)
_URL_HOST = re.compile(r"https?://(?:www\.)?([a-z0-9][a-z0-9.-]+\.[a-z]{2,})", re.I)


def normalize_browser_exe(exe: str | None) -> str:
    raw = (exe or "").strip().lower().replace("\\", "/").split("/")[-1]
    if raw in _BROWSER_LABELS:
        return raw
    if raw.endswith(".exe") and any(k.startswith(raw.replace(".exe", "")) for k in _BROWSER_LABELS):
        return raw
    return raw


def browser_display_name(exe: str | None) -> str:
    """Human label for stats UI — msedge.exe → Microsoft Edge."""
    key = normalize_browser_exe(exe)
    if key in _BROWSER_LABELS:
        return _BROWSER_LABELS[key]
    if key.endswith(".exe"):
        return key[:-4]
    return key or "Browser"


def domain_from_window_title(title: str | None) -> str | None:
    """Recover domain from titles like 'Page · youtube.com' or embedded URL."""
    t = (title or "").strip()
    if not t:
        return None
    m = _DOMAIN_IN_TITLE.search(t)
    if m:
        return m.group(1).lower().removeprefix("www.")
    m = _DOMAIN_ANYWHERE.search(t)
    if m:
        return m.group(1).lower().removeprefix("www.")
    m = _URL_HOST.search(t)
    if m:
        return m.group(1).lower().removeprefix("www.")
    return None
