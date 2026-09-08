"""Publish SoftLand-adjacent flags to enforcer_policy.json — JSON only.

Focus UI owns OS arm + kill list (hard_block_armed / exes).
Gate SoftLand only refreshes incubation_active when a policy file already exists,
so Productivity \"Armed\" cannot overwrite Focus Enforcer.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from backend.behavior.enforcer_files import EnforcerLockError, read_policy_file, write_policy_file

log = logging.getLogger("calt.enforcer_runtime")


def publish_enforcer_runtime(
    db: Session,
    user_id: int,
    *,
    gate: dict[str, Any] | None = None,
    policy: dict[str, Any] | None = None,
) -> None:
    """Update enforcer_policy.json for native. Never raises."""
    try:
        g = gate if isinstance(gate, dict) else {}
        pol = policy if isinstance(policy, dict) else {}
        if not pol:
            try:
                from backend.behavior.productivity_policy import load_policy_dict

                pol = load_policy_dict(db, int(user_id))
            except Exception:  # noqa: BLE001
                pol = {}

        inc = g.get("incubation") if isinstance(g.get("incubation"), dict) else {}
        incubating = bool(inc.get("active") or (g.get("browser") or {}).get("incubation_active"))

        existing = read_policy_file()
        if existing is not None:
            # Focus owns arm + exes; SoftLand only pushes incubation.
            write_policy_file(
                hard_block_armed=bool(existing.get("hard_block_armed")),
                gate_locked=bool(existing.get("gate_locked")),
                incubation_active=incubating,
                exes=list(existing.get("exes") or []),
                note="published_from_gate_incubation",
                preserve_lock_fields=True,
            )
            return

        # No Focus policy yet — seed DISARMED. SoftLand must never arm OS kills.
        exes = list(pol.get("hard_block_exes") or g.get("hard_block_exes") or [])
        write_policy_file(
            hard_block_armed=False,
            gate_locked=False,
            incubation_active=incubating,
            exes=exes,
            note="published_from_gate_seed_disarmed",
        )
    except EnforcerLockError as exc:
        log.info("publish_enforcer_runtime: strong lock blocked write: %s", exc)
    except Exception as exc:  # noqa: BLE001
        log.debug("publish_enforcer_runtime skipped: %s", exc)
