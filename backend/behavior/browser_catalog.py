"""Edge-only browser catalog — allowed vs known browsers vs installers.

Desktop tracker soft-locks unauthorized browsers and installers while the gate
enforces. Never process-kill (see PROTECTED merge in distraction_gate).
"""

from __future__ import annotations

import re

# Only Microsoft Edge is allowed while bible/planning/study (or Armed).
ALLOWED_BROWSER_EXES: frozenset[str] = frozenset({"msedge.exe"})

KNOWN_BROWSER_EXES: frozenset[str] = frozenset(
    {
        "msedge.exe",
        "chrome.exe",
        "firefox.exe",
        "brave.exe",
        "opera.exe",
        "opera_gx.exe",
        "vivaldi.exe",
        "arc.exe",
        "zen.exe",
        "zen browser.exe",
        "chromium.exe",
        "iexplore.exe",
        "waterfox.exe",
        "librewolf.exe",
        "floorp.exe",
        "duckduckgo.exe",
        "tor.exe",
        "firefox-esr.exe",
        "sidekick.exe",
        "maxthon.exe",
        "iridium.exe",
        "slimjet.exe",
        "seamonkey.exe",
        "pale moon.exe",
        "palemoon.exe",
        "basilisk.exe",
        "yandex.exe",
    }
)

# Exact installer / setup process names (normalized lowercase).
BROWSER_INSTALLER_EXES: frozenset[str] = frozenset(
    {
        "chromesetup.exe",
        "chrome_installer.exe",
        "minichrome.exe",
        "firefox installer.exe",
        "firefox setup.exe",
        "firefoxsetup.exe",
        "bravesetup.exe",
        "brave_installer.exe",
        "operasetup.exe",
        "opera_installer.exe",
        "vivaldisetup.exe",
        "vivaldi_installer.exe",
        "arcinstaller.exe",
        "zen_installer.exe",
        "zenbrowser.exe",
        "zen browser setup.exe",
        "waterfox setup.exe",
        "librewolf setup.exe",
        "floorp setup.exe",
        "torbrowser-install.exe",
        "tor browser setup.exe",
        "ddgbrowserinstaller.exe",
        "microsoftedgesetup.exe",  # Edge updater/setup — still soft-lock if user runs standalone setup mid-study? Allow Edge itself; setup can soft-lock to discourage reinstall loops — skip Edge setup from unauthorized
    }
)

# Heuristic patterns for installer-like names (after normalize_exe).
_INSTALLER_NAME_RE = re.compile(
    r"(?:"
    r"chromesetup|chrome.?installer|chrome.?standalone|"
    r"firefox.?installer|firefox.?setup|"
    r"brave.?setup|brave.?installer|"
    r"opera.?setup|opera.?installer|"
    r"vivaldi.?setup|vivaldi.?installer|"
    r"zen.?installer|zen.?setup|zenbrowser.?setup|"
    r"tor.?browser.?setup|torbrowser.?install|"
    r"waterfox.?setup|librewolf.?setup|floorp.?setup|"
    r"browser.?setup|browser.?installer"
    r")",
    re.I,
)

# Do not soft-lock Edge's own updater as "unauthorized browser install".
_EDGE_SETUP_EXES: frozenset[str] = frozenset(
    {
        "microsoftedgesetup.exe",
        "microsoftedgeupdate.exe",
        "microsoftedgeupdatecore.exe",
        "microsoftedge_x64.exe",
    }
)


def normalize_exe(exe: str | None) -> str:
    name = (exe or "").strip().lower()
    if "\\" in name or "/" in name:
        name = name.replace("\\", "/").rsplit("/", 1)[-1]
    return name


def is_allowed_browser(exe: str | None) -> bool:
    return normalize_exe(exe) in ALLOWED_BROWSER_EXES


def is_known_browser(exe: str | None) -> bool:
    return normalize_exe(exe) in KNOWN_BROWSER_EXES


def is_browser_installer(exe: str | None) -> bool:
    """True for common browser installer/setup process names."""
    name = normalize_exe(exe)
    if not name or name in _EDGE_SETUP_EXES:
        return False
    if name in BROWSER_INSTALLER_EXES:
        return True
    # Strip spaces for pattern check ("Firefox Installer.exe" → already spaced)
    compact = name.replace(" ", "")
    if _INSTALLER_NAME_RE.search(name) or _INSTALLER_NAME_RE.search(compact):
        # Avoid matching bare firefox.exe / chrome.exe as installers
        if name in KNOWN_BROWSER_EXES:
            return False
        return True
    return False


def is_unauthorized_browser(exe: str | None) -> bool:
    """Known non-Edge browser or browser installer → soft-lock while enforcing."""
    name = normalize_exe(exe)
    if not name or name in ALLOWED_BROWSER_EXES:
        return False
    if is_browser_installer(name):
        return True
    return name in KNOWN_BROWSER_EXES and name not in ALLOWED_BROWSER_EXES


def unauthorized_kind(exe: str | None) -> str | None:
    """Return alert kind: browser_installer | unauthorized_browser | None."""
    name = normalize_exe(exe)
    if not name or name in ALLOWED_BROWSER_EXES:
        return None
    if is_browser_installer(name):
        return "browser_installer"
    if name in KNOWN_BROWSER_EXES:
        return "unauthorized_browser"
    return None


def protected_browser_exes() -> frozenset[str]:
    """All catalog browsers + installers + Edge helpers — never process-kill.

    Edge is the allowed study browser; killing msedge.exe (or helpers) would look
    like the browser 'closing constantly'. Soft-lock unauthorized browsers only.
    """
    edge_helpers = frozenset(
        {
            "msedge.exe",
            "msedgewebview2.exe",
            "msedge_proxy.exe",
            "microsoftedge.exe",
            "microsoftedgecp.exe",
            "identity_helper.exe",  # Edge identity helper (when named alone)
        }
    )
    return frozenset(KNOWN_BROWSER_EXES | BROWSER_INSTALLER_EXES | _EDGE_SETUP_EXES | edge_helpers)


def catalog_payload() -> dict[str, list[str]]:
    """Lists for distraction-gate browser section / Settings UI."""
    return {
        "allowed_browsers": sorted(ALLOWED_BROWSER_EXES),
        "known_browsers": sorted(KNOWN_BROWSER_EXES),
        "browser_installers": sorted(BROWSER_INSTALLER_EXES),
    }
