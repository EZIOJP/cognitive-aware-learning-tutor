"""Native enforcer policy + status files (zero-Python tracker contract).

Paths under data/behavior/:
  enforcer_policy.json  — Focus / gate may write; calt_enforcer reads
  enforcer_status.json  — calt_enforcer writes; Focus / API only read

Python must never be required for the enforcer process itself.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from backend.paths import ROOT

log = logging.getLogger("calt.enforcer_files")

BEHAVIOR_DIR = ROOT / "data" / "behavior"
POLICY_PATH = BEHAVIOR_DIR / "enforcer_policy.json"
STATUS_PATH = BEHAVIOR_DIR / "enforcer_status.json"
LOCK_PATH = BEHAVIOR_DIR / "enforcer_owner.lock"

LOCK_MODES = frozenset({"none", "timer", "password", "phrase"})


class EnforcerLockError(Exception):
    """Raised when disarm is refused by a strong lock mode."""


def _clean_exes(exes: list[Any] | None) -> list[str]:
    cleaned: list[str] = []
    for x in exes or []:
        s = str(x).strip().strip('"').replace("\\", "/").split("/")[-1].lower()
        if s and s not in cleaned:
            cleaned.append(s)
    return cleaned


def read_policy_file() -> dict[str, Any] | None:
    try:
        if not POLICY_PATH.is_file():
            return None
        raw = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else None
    except Exception as exc:  # noqa: BLE001
        log.debug("read_policy_file: %s", exc)
        return None


def lock_blocks_disarm(
    existing: dict[str, Any] | None,
    *,
    provided_unlock: str = "",
) -> str | None:
    """Return error message if existing strong lock blocks disarm; else None."""
    if not existing:
        return None
    if not (existing.get("hard_block_armed") or existing.get("gate_locked")):
        return None
    mode = str(existing.get("lock_mode") or "none").strip().lower()
    if mode not in LOCK_MODES or mode == "none":
        return None

    if mode == "timer":
        try:
            until_i = int(existing.get("lock_until_unix") or 0)
        except (TypeError, ValueError):
            until_i = 0
        if until_i > 0 and time.time() < until_i:
            left = int(until_i - time.time())
            return f"Timer lock active — {left}s remaining before disarm is allowed"
        return None

    unlock = str(provided_unlock or "")
    if mode == "password":
        expected = str(existing.get("unlock_password") or "")
        if expected and unlock != expected:
            return "Password lock active — provide the unlock password to disarm"
        return None

    if mode == "phrase":
        expected = str(existing.get("unlock_phrase") or "")
        if expected and unlock.strip() != expected.strip():
            return "Phrase lock active — type the exact unlock phrase to disarm"
        return None

    return None


def write_policy_file(
    *,
    hard_block_armed: bool,
    gate_locked: bool,
    incubation_active: bool = False,
    exes: list[str] | None = None,
    note: str = "",
    lock_mode: str | None = None,
    lock_until_unix: int | None = None,
    unlock_password: str | None = None,
    unlock_phrase: str | None = None,
    anti_tamper: bool | None = None,
    provided_unlock: str = "",
    preserve_lock_fields: bool = False,
    protect_uninstall: bool | None = None,
) -> dict[str, Any]:
    """Write enforcer_policy.json for native calt_enforcer.

    Strong locks (timer / password / phrase) block disarm until satisfied.
    ``preserve_lock_fields`` keeps sticky lock secrets when SoftLand republishes.
    ``protect_uninstall`` (option B): hide Apps & features uninstall while on.
    """
    BEHAVIOR_DIR.mkdir(parents=True, exist_ok=True)
    existing = read_policy_file() or {}

    # Changing protect_uninstall off requires unlock when currently protected.
    if protect_uninstall is False and existing.get("protect_uninstall"):
        reason = None
        try:
            from backend.behavior.uninstall_protect import verify_uninstall_unlock

            reason = verify_uninstall_unlock(existing, provided_unlock)
        except Exception:
            reason = None
        if reason:
            raise EnforcerLockError(reason)

    wants_protect = (
        bool(protect_uninstall)
        if protect_uninstall is not None
        else bool(existing.get("protect_uninstall"))
    )

    wants_full_disarm = (not hard_block_armed) and (not gate_locked)
    if wants_full_disarm or ((not hard_block_armed) or (not gate_locked)):
        # Any attempt to turn off arm or lock while sticky lock is active.
        if (not hard_block_armed) or (not gate_locked):
            reason = lock_blocks_disarm(existing, provided_unlock=provided_unlock)
            if reason:
                raise EnforcerLockError(reason)

    # Kill-list mutation while armed + active lock = same bypass as Disarm.
    cleaned_candidate = _clean_exes(exes if exes is not None else existing.get("exes"))
    existing_exes = _clean_exes(existing.get("exes"))
    if cleaned_candidate != existing_exes and bool(existing.get("hard_block_armed")):
        reason = lock_blocks_disarm(existing, provided_unlock=provided_unlock)
        if reason:
            raise EnforcerLockError(
                "Kill list locked while armed — unlock/disarm first (same as Disarm)"
            )

    # Resolve lock fields
    if wants_full_disarm:
        mode = "none"
        until_val = 0
        # Keep unlock secrets when protect-uninstall stays on (reuse same password).
        if wants_protect:
            pwd = (
                str(unlock_password)
                if unlock_password is not None
                else str(existing.get("unlock_password") or "")
            )
            phrase = (
                str(unlock_phrase)
                if unlock_phrase is not None
                else str(existing.get("unlock_phrase") or "")
            )
        else:
            pwd = ""
            phrase = ""
        at = bool(anti_tamper) if anti_tamper is not None else True
    elif preserve_lock_fields and existing:
        mode = str(existing.get("lock_mode") or "none").strip().lower()
        if mode not in LOCK_MODES:
            mode = "none"
        try:
            until_val = int(existing.get("lock_until_unix") or 0)
        except (TypeError, ValueError):
            until_val = 0
        pwd = str(existing.get("unlock_password") or "")
        phrase = str(existing.get("unlock_phrase") or "")
        at = bool(existing.get("anti_tamper", True)) if anti_tamper is None else bool(anti_tamper)
    else:
        mode = str(lock_mode if lock_mode is not None else existing.get("lock_mode") or "none").strip().lower()
        if mode not in LOCK_MODES:
            mode = "none"
        if lock_until_unix is not None:
            try:
                until_val = int(lock_until_unix)
            except (TypeError, ValueError):
                until_val = 0
        else:
            try:
                until_val = int(existing.get("lock_until_unix") or 0) if mode == "timer" else 0
            except (TypeError, ValueError):
                until_val = 0
        if unlock_password is not None:
            pwd = str(unlock_password)
        elif mode == "password" or wants_protect:
            pwd = str(existing.get("unlock_password") or "")
        else:
            pwd = ""
        if unlock_phrase is not None:
            phrase = str(unlock_phrase)
        elif mode == "phrase" or wants_protect:
            phrase = str(existing.get("unlock_phrase") or "")
        else:
            phrase = ""
        if anti_tamper is not None:
            at = bool(anti_tamper)
        elif "anti_tamper" in existing:
            at = bool(existing.get("anti_tamper"))
        else:
            at = True

    if wants_protect and not (pwd.strip() or phrase.strip()):
        raise EnforcerLockError(
            "Protect uninstall needs an unlock password or phrase — set one in Focus first"
        )

    cleaned = cleaned_candidate

    payload: dict[str, Any] = {
        "hard_block_armed": bool(hard_block_armed),
        "gate_locked": bool(gate_locked),
        "incubation_active": bool(incubation_active),
        "exes": cleaned,
        "note": str(note or "")[:120],
        "lock_mode": mode,
        "lock_until_unix": until_val,
        "unlock_password": pwd[:128],
        "unlock_phrase": phrase[:256],
        "anti_tamper": at,
        "protect_uninstall": bool(wants_protect),
    }
    POLICY_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    # Sync ARP hide/show + small state file for Uninstall.bat (best-effort).
    try:
        from backend.behavior import uninstall_protect as up

        up.write_protect_state_file(payload)
        if protect_uninstall is not None or bool(existing.get("protect_uninstall")) != wants_protect:
            up.apply_protect_uninstall(protect=wants_protect)
    except Exception as exc:  # noqa: BLE001
        log.debug("protect_uninstall sync: %s", exc)

    return payload


def read_status_file() -> dict[str, Any] | None:
    """Prefer native-written status. Returns None if missing/stale-unreadable."""
    try:
        if not STATUS_PATH.is_file():
            return None
        raw = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else None
    except Exception as exc:  # noqa: BLE001
        log.debug("read_status_file: %s", exc)
        return None


def status_age_seconds() -> float | None:
    try:
        if not STATUS_PATH.is_file():
            return None
        return max(0.0, time.time() - STATUS_PATH.stat().st_mtime)
    except OSError:
        return None
