"""Option B uninstall protect — hide Apps & features entry while locked.

Uses HKCU Uninstall key for Inno AppId. Password reuse: enforcer unlock_password /
unlock_phrase. SoftLand never Arms; this only gates product uninstall.
"""

from __future__ import annotations

import json
import logging
import winreg
from typing import Any

log = logging.getLogger("calt.uninstall_protect")

# Must match scripts/desktop_tracker/installer/install_calt_desktop.iss AppId
INNO_APP_ID = "{A7C4D5E1-9B2F-4E8A-9C31-0C1A2B3C4D5E}_is1"
UNINSTALL_KEY = rf"Software\Microsoft\Windows\CurrentVersion\Uninstall\{INNO_APP_ID}"
BACKUP_KEY = r"Software\CALT\Productivity"
BACKUP_UNINSTALL = "UninstallStringBackup"
BACKUP_QUIET = "QuietUninstallStringBackup"
BACKUP_DISPLAY = "DisplayNameBackup"


def _open_uninstall(write: bool = False):
    access = winreg.KEY_READ | (winreg.KEY_SET_VALUE if write else 0)
    return winreg.OpenKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY, 0, access)


def _get_str(key, name: str) -> str | None:
    try:
        val, _ = winreg.QueryValueEx(key, name)
        return str(val) if val else None
    except OSError:
        return None


def _set_str(key, name: str, value: str) -> None:
    winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)


def _set_dword(key, name: str, value: int) -> None:
    winreg.SetValueEx(key, name, 0, winreg.REG_DWORD, int(value))


def _del_value(key, name: str) -> None:
    try:
        winreg.DeleteValue(key, name)
    except OSError:
        pass


def uninstall_entry_exists() -> bool:
    try:
        with _open_uninstall(False):
            return True
    except OSError:
        return False


def apply_protect_uninstall(*, protect: bool) -> dict[str, Any]:
    """Hide (protect=True) or restore (protect=False) Inno ARP uninstall entry."""
    out: dict[str, Any] = {"ok": False, "protect": bool(protect), "arp_present": False}
    try:
        with _open_uninstall(True) as uk:
            out["arp_present"] = True
            backup = winreg.CreateKey(winreg.HKEY_CURRENT_USER, BACKUP_KEY)
            try:
                if protect:
                    u = _get_str(uk, "UninstallString")
                    q = _get_str(uk, "QuietUninstallString")
                    d = _get_str(uk, "DisplayName")
                    if u:
                        _set_str(backup, BACKUP_UNINSTALL, u)
                    if q:
                        _set_str(backup, BACKUP_QUIET, q)
                    if d:
                        _set_str(backup, BACKUP_DISPLAY, d)
                    # Hide from Apps & features (SystemComponent=1)
                    _set_dword(uk, "SystemComponent", 1)
                    # Neutralize direct uninstall strings
                    _set_str(
                        uk,
                        "UninstallString",
                        'cmd.exe /c echo CALT uninstall protected — unlock in Focus Settings & pause',
                    )
                    _del_value(uk, "QuietUninstallString")
                    out["ok"] = True
                    out["hidden"] = True
                else:
                    # Restore
                    try:
                        u = _get_str(backup, BACKUP_UNINSTALL)
                        q = _get_str(backup, BACKUP_QUIET)
                        if u:
                            _set_str(uk, "UninstallString", u)
                        if q:
                            _set_str(uk, "QuietUninstallString", q)
                    except OSError:
                        pass
                    _set_dword(uk, "SystemComponent", 0)
                    _del_value(uk, "SystemComponent")
                    out["ok"] = True
                    out["hidden"] = False
            finally:
                winreg.CloseKey(backup)
    except OSError as exc:
        out["error"] = str(exc)
        log.debug("apply_protect_uninstall: %s", exc)
    return out


def verify_uninstall_unlock(policy: dict[str, Any] | None, provided: str) -> str | None:
    """Return error if protect_uninstall is on and unlock fails; else None."""
    if not policy or not policy.get("protect_uninstall"):
        return None
    pwd = str(policy.get("unlock_password") or "")
    phrase = str(policy.get("unlock_phrase") or "")
    provided = str(provided or "")
    if pwd and provided == pwd:
        return None
    if phrase and provided.strip() == phrase.strip():
        return None
    if not pwd and not phrase:
        return "Protect uninstall is on but no unlock password/phrase is set — set one in Focus"
    return "Uninstall protected — enter Focus unlock password or phrase"


def read_protect_state_file() -> dict[str, Any]:
    """Small helper JSON for Uninstall.bat (same folder as enforcer_policy)."""
    from backend.behavior.enforcer_files import BEHAVIOR_DIR

    path = BEHAVIOR_DIR / "uninstall_protect.json"
    try:
        if path.is_file():
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                return raw
    except Exception:
        pass
    return {"protect_uninstall": False}


def write_protect_state_file(policy: dict[str, Any]) -> None:
    from backend.behavior.enforcer_files import BEHAVIOR_DIR

    BEHAVIOR_DIR.mkdir(parents=True, exist_ok=True)
    path = BEHAVIOR_DIR / "uninstall_protect.json"
    path.write_text(
        json.dumps(
            {
                "protect_uninstall": bool(policy.get("protect_uninstall")),
                "has_password": bool(policy.get("unlock_password")),
                "has_phrase": bool(policy.get("unlock_phrase")),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def cli_allow_uninstall(provided_unlock: str) -> int:
    """Exit code helper for Uninstall.bat: 0 = proceed (ARP restored), 1 = blocked."""
    from backend.behavior.enforcer_files import read_policy_file, write_policy_file

    pol = read_policy_file() or {}
    if not pol.get("protect_uninstall"):
        print("Uninstall protect is off — proceeding.")
        return 0
    err = verify_uninstall_unlock(pol, provided_unlock)
    if err:
        print(err, flush=True)
        return 1
    # Clear protect + restore ARP (password already verified).
    write_policy_file(
        hard_block_armed=bool(pol.get("hard_block_armed")),
        gate_locked=bool(pol.get("gate_locked")),
        incubation_active=bool(pol.get("incubation_active")),
        exes=list(pol.get("exes") or []),
        note="uninstall_bat_unlock",
        preserve_lock_fields=True,
        protect_uninstall=False,
        provided_unlock=provided_unlock,
    )
    print("Uninstall protect cleared — Apps & features entry restored.")
    return 0
