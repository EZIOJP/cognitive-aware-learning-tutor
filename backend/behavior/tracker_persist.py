"""HKCU Run + Startup protect helpers for desktop tracker (user-level only)."""

from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path

log = logging.getLogger("desktop_tracker")

ROOT = Path(__file__).resolve().parents[2]
RUN_VALUE_NAME = "CALT Desktop Tracker"
AUTOSTART_BAT = ROOT / "scripts" / "desktop_tracker" / "tracker_autostart.bat"

_last_protect_at = 0.0
PROTECT_GAP_S = 180.0  # re-assert Run key every ~3 min while armed


def persistence_protect_enabled() -> bool:
    return os.environ.get("TRACKER_PERSIST_PROTECT", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def _run_command() -> str:
    """Command string for HKCU\\...\\Run (quoted paths)."""
    pyw = ROOT / ".venv" / "Scripts" / "pythonw.exe"
    if not pyw.is_file():
        pyw = ROOT / ".venv" / "Scripts" / "python.exe"
    vbs = ROOT / "scripts" / "desktop_tracker" / "tracker_tray_launch.vbs"
    if vbs.is_file() and pyw.is_file():
        return f'wscript.exe //B "{vbs}" "{pyw}"'
    if AUTOSTART_BAT.is_file():
        return f'"{AUTOSTART_BAT}"'
    return f'"{sys.executable}" -m backend.behavior.desktop_tracker'


def ensure_hkcu_run_key() -> bool:
    """Create/update HKCU Run entry. Returns True on success."""
    if sys.platform != "win32":
        return False
    try:
        import winreg

        cmd = _run_command()
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_SET_VALUE,
        )
        try:
            winreg.SetValueEx(key, RUN_VALUE_NAME, 0, winreg.REG_SZ, cmd)
        finally:
            winreg.CloseKey(key)
        return True
    except Exception as exc:  # noqa: BLE001
        log.debug("HKCU Run ensure failed: %s", exc)
        return False


def remove_hkcu_run_key() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_SET_VALUE,
        )
        try:
            winreg.DeleteValue(key, RUN_VALUE_NAME)
        except FileNotFoundError:
            pass
        finally:
            winreg.CloseKey(key)
        return True
    except Exception as exc:  # noqa: BLE001
        log.debug("HKCU Run remove failed: %s", exc)
        return False


def maybe_protect_startup(*, armed: bool = True) -> None:
    """While Armed + protect on, re-add Run key periodically (discourage casual uninstall)."""
    global _last_protect_at
    if not armed or not persistence_protect_enabled():
        return
    now = time.time()
    if now - _last_protect_at < PROTECT_GAP_S:
        return
    _last_protect_at = now
    if ensure_hkcu_run_key():
        log.debug("Persistence protect: HKCU Run refreshed")
