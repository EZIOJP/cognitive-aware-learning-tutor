"""Who owns hard-block process kills: native calt_enforcer vs legacy Python.

DESKTOP TRACKER RULE: calt_enforcer owns kills with ZERO Python runtime.
Python TrackerService must not kill unless explicitly opted in (CALT_UI_KILLS=1).
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from backend.paths import ROOT

LOCK_PATH = ROOT / "data" / "behavior" / "enforcer_owner.lock"
_STALE_S = 30.0
_HEARTBEAT_EVERY_S = 5.0


def _env_force_ui_kills() -> bool:
    """Emergency escape hatch: allow legacy Python TrackerService kills."""
    return os.environ.get("CALT_UI_KILLS", "").strip().lower() in ("1", "true", "yes")


def _env_force_service_owner() -> bool:
    return os.environ.get("CALT_ENFORCER_OWNS_KILLS", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def claim_ownership(*, pid: int | None = None) -> None:
    """Enforcer process: mark that it owns kills (heartbeat refreshed by tick)."""
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    pid = int(pid if pid is not None else os.getpid())
    LOCK_PATH.write_text(f"{pid}\n{time.time():.3f}\n", encoding="utf-8")


def refresh_ownership_heartbeat() -> None:
    claim_ownership()


def release_ownership() -> None:
    try:
        if LOCK_PATH.is_file():
            LOCK_PATH.unlink()
    except OSError:
        pass


def ownership_active(*, stale_after_s: float = _STALE_S) -> bool:
    """True if enforcer claimed ownership recently (or env forces service owner)."""
    if _env_force_ui_kills():
        return False
    if _env_force_service_owner():
        return True
    if not LOCK_PATH.is_file():
        return False
    try:
        lines = LOCK_PATH.read_text(encoding="utf-8").strip().splitlines()
        if len(lines) < 2:
            return False
        ts = float(lines[1])
    except (OSError, ValueError):
        return False
    return (time.time() - ts) <= stale_after_s


def enforcer_owns_kills() -> bool:
    """TrackerService must skip process kills when True.

    Default True (native owns kills). Set CALT_UI_KILLS=1 only for legacy
    Python kill fallback when native is unavailable.
    """
    if _env_force_ui_kills():
        return False
    return True


def enforcer_owns_tracking() -> bool:
    """True when native C++ writes tracked_sessions; Python must not double-persist."""
    return ownership_active()


def heartbeat_interval_s() -> float:
    return _HEARTBEAT_EVERY_S
