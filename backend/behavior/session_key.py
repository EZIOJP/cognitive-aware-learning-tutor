"""Stable session identity for desktop tracker grouping."""

from __future__ import annotations

import re

from backend.behavior.domain_classify import _BROWSER_SUFFIX, _TITLE_SITE_HINTS

_BROWSER_EXE = re.compile(
    r"chrome|msedge|firefox|brave|opera|arc|zen",
    re.I,
)


def is_browser_exe(exe: str) -> bool:
    return bool(_BROWSER_EXE.search(exe or ""))


def looks_like_domain(value: str | None) -> bool:
    """True for hostname-like app_name values (extension stores domain here)."""
    v = (value or "").strip().lower()
    if not v or " " in v:
        return False
    if v.startswith("calt_spa:") or v.endswith((".exe", ".app", ".dll")):
        return False
    if v.startswith(".") or v.endswith("."):
        return False
    return "." in v


def normalize_site_from_title(title: str) -> str:
    """Return a stable site label (e.g. youtube.com) from a browser window title."""
    cleaned = _BROWSER_SUFFIX.sub("", title or "").strip()
    for pattern, domain in _TITLE_SITE_HINTS:
        if re.search(pattern, cleaned, re.I):
            return domain
    parts = re.split(r"\s*[-–—]\s*", cleaned)
    if len(parts) > 1:
        hint = parts[-1].strip().lower().replace(" ", "")
        if hint and len(hint) > 2:
            return hint
    return "unknown"


def session_identity(exe: str, title: str) -> tuple[str, str]:
    """Return (group_key, domain_label) for session continuity.

    - Browsers: group by exe + site (title changes on same site do not split).
    - Other apps: group by exe only (title updates without splitting).
    """
    exe_l = (exe or "").lower()
    if is_browser_exe(exe):
        site = normalize_site_from_title(title)
        return f"{exe_l}|{site}", site
    return exe_l, exe or "unknown"
