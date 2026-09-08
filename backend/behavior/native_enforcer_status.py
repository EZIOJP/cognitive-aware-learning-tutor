"""Probe native C++ enforcer — prefer enforcer_status.json (zero-Python tracker)."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

from backend.paths import ROOT

_EXE_CANDIDATES = (
    ROOT / "native" / "calt_enforcer" / "build" / "Release" / "calt_enforcer.exe",
    ROOT / "native" / "calt_enforcer" / "build" / "calt_enforcer.exe",
)
_LOCK = ROOT / "data" / "behavior" / "enforcer_owner.lock"
_KILL_LOG = ROOT / "data" / "behavior" / "enforcer_kills.log"
_SERVICE = "CALTEnforcer"
_STATUS_STALE_S = 15.0


def native_exe_path() -> Path | None:
    for p in _EXE_CANDIDATES:
        if p.is_file():
            return p
    return None


def service_running() -> bool | None:
    if os.name != "nt":
        return None
    try:
        r = subprocess.run(
            ["sc.exe", "query", _SERVICE],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
        out = (r.stdout or "") + (r.stderr or "")
        if "FAILED" in out.upper() and "1060" in out:
            return False
        return "RUNNING" in out.upper()
    except Exception:  # noqa: BLE001
        return None


def last_kill_line() -> str:
    try:
        if not _KILL_LOG.is_file():
            return ""
        lines = _KILL_LOG.read_text(encoding="utf-8", errors="replace").strip().splitlines()
        return lines[-1] if lines else ""
    except OSError:
        return ""


def collect_native_enforcer_status() -> dict[str, Any]:
    """Focus / dashboard status. Prefer native JSON; fall back to lock + kill log."""
    from backend.behavior.enforcer_files import read_status_file, status_age_seconds

    exe = native_exe_path()
    file_st = read_status_file()
    age = status_age_seconds()
    fresh = file_st is not None and age is not None and age <= _STATUS_STALE_S

    owns = False
    try:
        from backend.behavior.enforcer_ownership import enforcer_owns_kills

        owns = bool(enforcer_owns_kills())
    except Exception:  # noqa: BLE001
        owns = False

    if fresh and file_st:
        last = str(file_st.get("last_kill") or "")[:160]
        if not last:
            last = last_kill_line()[:160]
        svc = file_st.get("service_running")
        if svc is None:
            svc = service_running()
        return {
            "native_exe_built": exe is not None,
            "native_exe_path": str(exe) if exe else "",
            "native_service_running": bool(svc) if svc is not None else service_running(),
            "enforcer_owns_kills": bool(file_st.get("owns", owns)),
            "enforcer_owns_tracking": bool(file_st.get("owns", owns)),
            "enforcer_lock_present": bool(file_st.get("lock_present", _LOCK.is_file())),
            "last_kill_log": last,
            "last_kill_exe": str(file_st.get("last_kill_exe") or ""),
            "armed": bool(file_st.get("armed")),
            "locked": bool(file_st.get("locked")),
            "policy_source": str(file_st.get("policy_source") or ""),
            "status_source": "enforcer_status.json",
            "status_age_s": age,
        }

    # Fallback when native not running / status file stale
    return {
        "native_exe_built": exe is not None,
        "native_exe_path": str(exe) if exe else "",
        "native_service_running": service_running(),
        "enforcer_owns_kills": owns,
        "enforcer_owns_tracking": owns,
        "enforcer_lock_present": _LOCK.is_file(),
        "last_kill_log": last_kill_line()[:160],
        "last_kill_exe": "",
        "armed": False,
        "locked": False,
        "policy_source": "",
        "status_source": "fallback",
        "status_age_s": age,
    }


def enforcer_maturity_block() -> dict[str, Any]:
    """Focus / Dashboard enforcer card — prefers native enforcer_status.json."""
    try:
        st = collect_native_enforcer_status()
    except Exception:  # noqa: BLE001
        st = {}
    return {
        "owns": bool(st.get("enforcer_owns_kills")),
        "exe_built": bool(st.get("native_exe_built")),
        "service_running": st.get("native_service_running"),
        "last_kill": str(st.get("last_kill_log") or ""),
        "last_kill_exe": str(st.get("last_kill_exe") or ""),
        "lock_present": bool(st.get("enforcer_lock_present")),
        "armed": bool(st.get("armed")),
        "locked": bool(st.get("locked")),
        "policy_source": str(st.get("policy_source") or ""),
        "status_source": str(st.get("status_source") or ""),
        "status_age_s": st.get("status_age_s"),
    }
