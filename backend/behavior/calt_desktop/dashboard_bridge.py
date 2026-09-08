"""Bridge JSON for CALT Desktop Dashboard (v2a) — gate → plain English."""

from __future__ import annotations

from typing import Any

from backend.behavior.calt_desktop.gate_summary import gate_lock_hint
from backend.behavior.tracker_rules import rules_snapshot_from_gate

_INCUBATION_TOTAL_SEC = 480
_EARNED_DAILY_CAP = 60


def _browser(gate: dict[str, Any]) -> dict[str, Any]:
    b = gate.get("browser")
    return b if isinstance(b, dict) else {}


def _morning(gate: dict[str, Any]) -> dict[str, Any]:
    m = gate.get("morning")
    return m if isinstance(m, dict) else {}


def _build_why(gate: dict[str, Any], snap_hint: str) -> str:
    browser = _browser(gate)
    morning = _morning(gate)

    if not gate.get("enabled"):
        return "Hard block is off — browsing follows your schedule."

    if browser.get("free_override_active"):
        return "PIN free-time override is active — entertainment unlocked for a while."

    if gate.get("day_unlimited") or gate.get("unlocked"):
        return "Day unlocked — follow your plan or browse per schedule."

    hint = str(morning.get("hint") or "").strip() or str(snap_hint or "").strip()
    if hint:
        return hint

    lock = gate_lock_hint(gate).strip()
    if lock:
        return lock

    nxt = str(morning.get("next") or "open").strip().lower()
    if nxt == "bible":
        return "Finish today's Bible chapter to unlock the plan."
    if nxt == "plan":
        return "Confirm today's plan to open the day."

    rem = gate.get("remaining_minutes")
    try:
        rem_i = int(rem) if rem is not None else 0
    except (TypeError, ValueError):
        rem_i = 0
    if rem_i > 0 and gate.get("locked"):
        return f"Earn {rem_i} more productive minutes to unlock the day."

    return "Gate is monitoring — check Rules if something feels blocked."


def _build_until(gate: dict[str, Any]) -> dict[str, str]:
    browser = _browser(gate)
    morning = _morning(gate)
    nxt = str(morning.get("next") or "open").strip().lower()

    if browser.get("free_override_active"):
        return {"kind": "free", "label": "Until free override ends"}

    if not gate.get("enabled"):
        return {"kind": "off", "label": "Hard block off"}

    if gate.get("day_unlimited") or (gate.get("unlocked") and nxt == "open"):
        return {"kind": "open", "label": "Day open"}

    if gate.get("locked") and nxt == "bible":
        return {"kind": "morning", "label": "Until Bible is done"}

    if gate.get("locked") and nxt == "plan":
        return {"kind": "morning", "label": "Until plan is confirmed"}

    try:
        rem = int(gate.get("remaining_minutes") or 0)
    except (TypeError, ValueError):
        rem = 0
    if rem > 0 and gate.get("locked"):
        return {"kind": "goal", "label": f"Until daily focus goal ({rem} min left)"}

    if gate.get("locked"):
        return {"kind": "locked", "label": "Until gate unlocks"}

    return {"kind": "open", "label": "Day open"}


def _build_blocked_summary(gate: dict[str, Any]) -> list[str]:
    browser = _browser(gate)
    items: list[str] = []

    if browser.get("free_override_active"):
        if browser.get("block_porn", True):
            items.append("Device porn hosts on")
        return items or ["Free override — most leisure allowed"]

    armed = bool(gate.get("enabled"))
    if not armed:
        if browser.get("block_porn", True):
            items.append("Device porn hosts on")
        return items or ["Hard block disarmed"]

    gaming = bool(gate.get("hard_block_gaming", True))
    exes = gate.get("hard_block_exes") or []
    if gaming or (isinstance(exes, list) and exes):
        items.append("Games & listed apps")

    enforce = bool(browser.get("enforce")) or bool(gate.get("locked"))
    mode = str(browser.get("mode") or gate.get("browser_mode") or "").strip().lower()
    if enforce or mode in ("bible", "planning", "study"):
        items.append("Leisure sites (SoftLand)")

    if browser.get("block_porn", True) or browser.get("force_porn_hosts"):
        items.append("Device porn hosts on")

    return items


def snapshot_from_gate(gate: dict[str, Any] | None) -> dict[str, Any]:
    """Pure mapping: distraction-gate JSON → Dashboard Bridge JSON (v2a)."""
    g = gate if isinstance(gate, dict) else {}
    rules = rules_snapshot_from_gate(g)
    browser = _browser(g)
    morning = _morning(g)
    nxt = str(morning.get("next") or rules.next_key or "open").strip().lower()

    mode_lbl = str(browser.get("mode_label") or rules.browser_mode_label or "FREE")
    # Prefer readable title case for Dashboard ("Study") over ALL-CAPS tray labels.
    if mode_lbl.isupper() and len(mode_lbl) > 1:
        mode_lbl = mode_lbl.title()

    why = _build_why(g, rules.hint)
    until = _build_until(g)
    blocked = _build_blocked_summary(g)

    free_on = bool(browser.get("free_override_active"))
    incubation_active = False  # v2c wires real incubation state
    incubation_blocks_pin = bool(incubation_active)  # Q4/D1 prep
    can_pin = bool(g.get("enabled")) and not free_on and not incubation_blocks_pin

    return {
        "active": {
            "hard_block_armed": bool(g.get("enabled")),
            "browser_mode_label": mode_lbl,
            "morning_next": nxt,
            "why": why,
            "until": until,
            "blocked_summary": blocked,
        },
        "incubation": {
            "active": incubation_active,
            "remaining_sec": 0,
            "total_sec": _INCUBATION_TOTAL_SEC,
        },
        "earned": {
            "balance_minutes": 0,
            "daily_earned": 0,
            "daily_cap": _EARNED_DAILY_CAP,
        },
        "actions": {
            "can_spend_earned": False,
            "can_pin_free": can_pin,
            "incubation_blocks_pin": incubation_blocks_pin,
        },
        "enforcer": {
            "owns": False,
            "exe_built": False,
            "service_running": None,
            "last_kill": "",
            "lock_present": False,
        },
    }


def snapshot_for_user(user_id: int, db: Any = None) -> dict[str, Any]:
    """Load live gate for ``user_id`` then map via :func:`snapshot_from_gate`.

    Enriches incubation + earned ledger when break_reward DB is available.
    """
    from backend.behavior.distraction_gate import compute_distraction_gate

    own_session = db is None
    if own_session:
        from backend.db.base import SessionLocal

        db = SessionLocal()
    try:
        gate = compute_distraction_gate(db, int(user_id))
        snap = snapshot_from_gate(gate)
        try:
            from backend.behavior import break_reward as br

            cfg = br.load_config()
            br.tick_incubation(int(user_id), db=db)
            inc = br.incubation_status(int(user_id), db=db, config=cfg)
            bal = br.balance(int(user_id), db=db)
            daily = br.daily_earned(int(user_id), db=db)
            cap = int(cfg.get("daily_earn_cap") or _EARNED_DAILY_CAP)
            inc_active = bool(inc.get("active"))
            free_on = bool((_browser(gate)).get("free_override_active"))
            can_pin = bool(gate.get("enabled")) and not free_on and not inc_active
            snap["incubation"] = {
                "active": inc_active,
                "remaining_sec": int(inc.get("remaining_sec") or 0),
                "total_sec": int(inc.get("total_sec") or cfg.get("break_minutes", 8) * 60),
            }
            snap["earned"] = {
                "balance_minutes": int(bal),
                "daily_earned": int(daily),
                "daily_cap": cap,
            }
            snap["actions"] = {
                "can_spend_earned": bal > 0 and not inc_active,
                "can_pin_free": can_pin,
                "incubation_blocks_pin": inc_active,
            }
        except Exception:
            pass
        try:
            from backend.behavior.native_enforcer_status import enforcer_maturity_block
            from backend.behavior.enforcer_files import read_policy_file

            snap["enforcer"] = enforcer_maturity_block()
            pol = read_policy_file() or {}
            snap["enforcer_policy"] = {
                "hard_block_armed": bool(pol.get("hard_block_armed")),
                "gate_locked": bool(pol.get("gate_locked")),
                "incubation_active": bool(pol.get("incubation_active")),
                "exes": list(pol.get("exes") or []),
                "lock_mode": str(pol.get("lock_mode") or "none"),
                "lock_until_unix": int(pol.get("lock_until_unix") or 0),
                "anti_tamper": bool(pol.get("anti_tamper", True)),
            }
        except Exception:
            snap.setdefault(
                "enforcer",
                {
                    "owns": False,
                    "exe_built": False,
                    "service_running": None,
                    "last_kill": "",
                    "lock_present": False,
                },
            )
            snap.setdefault(
                "enforcer_policy",
                {
                    "hard_block_armed": False,
                    "gate_locked": False,
                    "incubation_active": False,
                    "exes": [],
                },
            )
        return snap
    finally:
        if own_session:
            db.close()
