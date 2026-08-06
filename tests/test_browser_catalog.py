"""Edge-only browser catalog: allow Edge; soft-lock others + installers."""

from backend.behavior.browser_catalog import (
    is_allowed_browser,
    is_browser_installer,
    is_unauthorized_browser,
    normalize_exe,
    unauthorized_kind,
)


def test_normalize_strips_path():
    assert normalize_exe(r"C:\Program Files\Google\Chrome\Application\chrome.exe") == "chrome.exe"
    assert normalize_exe("ChromeSetup.EXE") == "chromesetup.exe"


def test_edge_allowed_chrome_not():
    assert is_allowed_browser("msedge.exe")
    assert not is_allowed_browser("chrome.exe")
    assert is_unauthorized_browser("chrome.exe")
    assert is_unauthorized_browser("firefox.exe")
    assert is_unauthorized_browser("zen.exe")
    assert not is_unauthorized_browser("msedge.exe")
    assert not is_unauthorized_browser("cursor.exe")


def test_installer_detection():
    assert is_browser_installer("ChromeSetup.exe")
    assert is_browser_installer("Firefox Installer.exe")
    assert is_browser_installer("BraveSetup.exe")
    assert is_unauthorized_browser("ChromeSetup.exe")
    assert unauthorized_kind("ChromeSetup.exe") == "browser_installer"
    assert unauthorized_kind("chrome.exe") == "unauthorized_browser"
    assert unauthorized_kind("msedge.exe") is None
    # Bare browser exe is not an installer
    assert not is_browser_installer("chrome.exe")
    assert not is_browser_installer("firefox.exe")
    # Edge's own updater is not treated as foreign installer
    assert not is_browser_installer("MicrosoftEdgeUpdate.exe")


def test_gate_section_includes_catalog():
    from backend.behavior.browser_gate_policy import build_browser_gate_section

    section = build_browser_gate_section(
        enabled=True,
        locked=True,
        morning_next="open",
        mode="study",
    )
    assert section["allowed_browsers"] == ["msedge.exe"]
    assert "chrome.exe" in section["known_browsers"]
    assert "chromesetup.exe" in section["browser_installers"]
    assert "Edge" in section["note"] or "edge" in section["note"].lower()
