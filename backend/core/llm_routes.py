"""Profile-based tier routing layered over llm_tiers."""

from __future__ import annotations

import json
import logging
from functools import lru_cache

from backend.config import get_settings
from backend.core.llm_tiers import ChainEntry, VALID_TIERS, _parse_chain_list, get_chain
from backend.paths import LLM_ROUTES_PATH

log = logging.getLogger(__name__)


@lru_cache
def load_route_profiles() -> dict[str, dict[str, list[ChainEntry]]]:
    if not LLM_ROUTES_PATH.is_file():
        return {}
    try:
        raw = json.loads(LLM_ROUTES_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("Could not load %s: %s", LLM_ROUTES_PATH, exc)
        return {}

    profiles_raw = raw.get("profiles", raw)
    if not isinstance(profiles_raw, dict):
        return {}

    profiles: dict[str, dict[str, list[ChainEntry]]] = {}
    for profile_name, profile_data in profiles_raw.items():
        if not isinstance(profile_data, dict):
            continue
        tiers: dict[str, list[ChainEntry]] = {}
        for tier_name in VALID_TIERS:
            parsed = _parse_chain_list(profile_data.get(tier_name, []))
            if parsed:
                tiers[tier_name] = parsed
        if tiers:
            profiles[profile_name.strip().lower()] = tiers
    return profiles


def get_active_route_profile(override: str | None = None) -> str:
    if override and override.strip():
        return override.strip().lower()
    profile = get_settings().llm_route_profile.strip().lower()
    return profile or "hybrid"


def get_chain_for_tier(tier: str, route_profile: str | None = None) -> list[ChainEntry]:
    profile_name = get_active_route_profile(route_profile)
    profiles = load_route_profiles()
    key = tier.strip().lower()
    if key not in VALID_TIERS:
        key = get_settings().llm_default_tier.strip().lower() or "medium"

    profile = profiles.get(profile_name)
    if profile and profile.get(key):
        return list(profile[key])
    return get_chain(key)

