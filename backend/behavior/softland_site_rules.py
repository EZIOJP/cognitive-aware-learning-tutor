"""User SoftLand site rules — Phase 2: SoT is softland_policy.json.

Legacy softland_site_rules.json is dual-written for compatibility.
"""

from __future__ import annotations

from typing import Any


def default_site_rules() -> dict[str, Any]:
    return {
        "allow_extra": [],
        "watch_extra": [],
        "block_extra": [],
    }


def load_site_rules() -> dict[str, Any]:
    from backend.behavior.softland_policy import site_rules_from_policy

    return site_rules_from_policy()


def save_site_rules(payload: dict[str, Any]) -> dict[str, Any]:
    from backend.behavior.softland_policy import patch_softland_policy

    sr: dict[str, Any] = {}
    for k in ("allow_extra", "watch_extra", "block_extra"):
        if k in payload:
            sr[k] = payload[k]
    data = patch_softland_policy({"site_rules": sr})
    return dict(data.get("site_rules") or default_site_rules())


def merge_allow(base: list[str]) -> list[str]:
    extra = load_site_rules().get("allow_extra") or []
    return list(dict.fromkeys([*(base or []), *extra]))


def merge_watch(base: list[str]) -> list[str]:
    rules = load_site_rules()
    extra = list(rules.get("watch_extra") or []) + list(rules.get("block_extra") or [])
    return list(dict.fromkeys([*(base or []), *extra]))
