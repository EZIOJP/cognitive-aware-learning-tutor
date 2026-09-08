"""CALT Desktop hard-block enforcer loop (no Qt UI required).

Polls productivity policy + distraction gate every few seconds and terminates
blocked processes using the same helpers as TrackerService.

Usage:
    python -m backend.behavior.enforcer_service

Env:
    TRACKER_USER_ID — optional override (same as desktop tracker)
    CALT_ENFORCER_POLL_S — poll interval seconds (default 3)
"""

from __future__ import annotations

import logging
import os
import signal
import threading
import time
from collections.abc import Callable
from typing import Any

from backend.behavior.enforcer_ownership import (
    claim_ownership,
    heartbeat_interval_s,
    refresh_ownership_heartbeat,
    release_ownership,
)
from backend.behavior.tracker_storage import TrackerConfig, resolve_user_id
from backend.paths import ROOT

log = logging.getLogger("calt_enforcer")

DEFAULT_POLL_S = 3.0
LOG_DIR = ROOT / "data" / "behavior"
_last_owner_heartbeat = 0.0


def resolve_enforcer_user_id() -> int:
    """Same user resolution as desktop tracker (config / TRACKER_USER_ID / admin)."""
    return resolve_user_id(TrackerConfig.load())


def _default_compute_gate(db: Any, user_id: int) -> dict[str, Any]:
    from backend.behavior.distraction_gate import compute_distraction_gate

    return compute_distraction_gate(db, user_id)


def _default_load_policy(db: Any, user_id: int) -> dict[str, Any]:
    from backend.behavior.productivity_policy import load_policy_dict

    return load_policy_dict(db, user_id)


def _default_list_blockable(policy: dict[str, Any]) -> list[tuple[int, str]]:
    from backend.behavior.distraction_gate import list_blockable_pids

    return list_blockable_pids(policy)


def _default_terminate(pid: int, *, exe: str = "") -> bool:
    from backend.behavior.distraction_gate import terminate_blocked_process

    return terminate_blocked_process(pid, exe=exe)


def enforce_once(
    *,
    user_id: int,
    db: Any | None = None,
    compute_gate: Callable[[Any, int], dict[str, Any]] | None = None,
    load_policy: Callable[[Any, int], dict[str, Any]] | None = None,
    list_blockable: Callable[[dict[str, Any]], list[tuple[int, str]]] | None = None,
    terminate: Callable[..., bool] | None = None,
) -> int:
    """One enforce tick. Returns number of successful kill attempts.

    Mirrors TrackerService hard-block: only kill when policy is armed and gate
    is locked. Reuses ``list_blockable_pids`` / ``terminate_blocked_process``.

    Q3 C2: while incubation is active, keep kills even if the gate is unlocked
    (force study-hard for the break duration).
    """
    compute_gate = compute_gate or _default_compute_gate
    load_policy = load_policy or _default_load_policy
    list_blockable = list_blockable or _default_list_blockable
    terminate = terminate or _default_terminate

    own_db = db is None
    if own_db:
        from backend.db.base import SessionLocal

        db = SessionLocal()
    incubating = False
    try:
        gate = compute_gate(db, user_id) or {}
        policy = load_policy(db, user_id) or {}
        try:
            from backend.behavior.break_reward import force_study_hard, tick_incubation

            tick_incubation(int(user_id), db=db)
            incubating = bool(force_study_hard(int(user_id), db=db))
        except Exception as exc:  # noqa: BLE001
            log.debug("enforcer incubation tick skipped: %s", exc)
            incubating = False
    finally:
        if own_db:
            db.close()

    if not policy.get("hard_block_enabled"):
        return 0
    # Normal path: only kill while locked. Incubation forces kills (C2).
    if not gate.get("locked") and not incubating:
        return 0

    targets = list_blockable(policy)
    killed = 0
    for pid, exe in targets:
        try:
            if terminate(pid, exe=exe):
                killed += 1
                log.info(
                    "enforcer killed pid=%s exe=%s%s",
                    pid,
                    exe,
                    " (incubation)" if incubating else "",
                )
        except Exception as exc:  # noqa: BLE001
            log.warning("enforcer terminate failed pid=%s: %s", pid, exe)
    return killed


def run_loop(
    *,
    user_id: int | None = None,
    poll_s: float | None = None,
    stop_event: threading.Event | None = None,
    max_iterations: int | None = None,
) -> int:
    """Poll until stop_event / SIGINT / SIGTERM. Returns 0 on clean stop."""
    uid = int(user_id if user_id is not None else resolve_enforcer_user_id())
    interval = float(
        poll_s
        if poll_s is not None
        else os.environ.get("CALT_ENFORCER_POLL_S", DEFAULT_POLL_S)
    )
    interval = max(2.0, min(5.0, interval)) if poll_s is None else max(0.01, interval)
    stop = stop_event or threading.Event()

    def _request_stop(*_args: Any) -> None:
        log.info("enforcer stop requested")
        stop.set()

    prev_int = None
    prev_term = None
    try:
        prev_int = signal.signal(signal.SIGINT, _request_stop)
    except (ValueError, OSError):
        prev_int = None
    if hasattr(signal, "SIGTERM"):
        try:
            prev_term = signal.signal(signal.SIGTERM, _request_stop)
        except (ValueError, OSError):
            prev_term = None

    log.info("enforcer started user_id=%s poll_s=%.2f (owns hard-block kills)", uid, interval)
    claim_ownership()
    global _last_owner_heartbeat
    _last_owner_heartbeat = time.time()
    iterations = 0
    try:
        while not stop.is_set():
            try:
                enforce_once(user_id=uid)
            except Exception as exc:  # noqa: BLE001
                log.warning("enforcer tick failed: %s", exc)
            now = time.time()
            if now - _last_owner_heartbeat >= heartbeat_interval_s():
                refresh_ownership_heartbeat()
                _last_owner_heartbeat = now
            iterations += 1
            if max_iterations is not None and iterations >= max_iterations:
                break
            stop.wait(interval)
    finally:
        release_ownership()
        if prev_int is not None:
            try:
                signal.signal(signal.SIGINT, prev_int)
            except (ValueError, OSError):
                pass
        if prev_term is not None and hasattr(signal, "SIGTERM"):
            try:
                signal.signal(signal.SIGTERM, prev_term)
            except (ValueError, OSError):
                pass
        log.info("enforcer stopped after %s tick(s)", iterations)
    return 0


def _configure_logging() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / "enforcer.log"
    handlers: list[logging.Handler] = [
        logging.StreamHandler(),
        logging.FileHandler(log_path, encoding="utf-8"),
    ]
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [calt_enforcer] %(message)s",
        datefmt="%H:%M:%S",
        handlers=handlers,
        force=True,
    )


def main(argv: list[str] | None = None) -> int:
    _ = argv  # reserved for future flags
    _configure_logging()
    return run_loop()
