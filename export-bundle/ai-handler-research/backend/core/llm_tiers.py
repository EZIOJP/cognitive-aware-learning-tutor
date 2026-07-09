"""Parse tier provider chains from data/llm_tiers.json or .env."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from functools import lru_cache

from backend.config import get_settings
from backend.core.ollama_client import _normalize_provider
from backend.paths import LLM_TIERS_PATH

log = logging.getLogger(__name__)

VALID_TIERS = ("light", "medium", "heavy")


@dataclass(frozen=True)
class ChainEntry:
    provider: str
    model: str
    base_url: str | None = None
    api_key: str | None = None
    max_context_chars: int | None = None


def parse_chain_entry(raw: str) -> ChainEntry | None:
    text = raw.strip()
    if not text or ":" not in text:
        return None
    provider, rest = text.split(":", 1)
    provider = _normalize_provider(provider.strip())
    rest = rest.strip()
    if not rest:
        return None
    if rest.startswith("http://") or rest.startswith("https://"):
        last_colon = rest.rfind(":")
        if last_colon <= 8:
            return None
        base_url = rest[:last_colon].strip().rstrip("/")
        model = rest[last_colon + 1 :].strip()
        if not model:
            return None
        return ChainEntry(provider=provider, model=model, base_url=base_url)
    return ChainEntry(provider=provider, model=rest, base_url=None)


def _parse_chain_list(items: list[str] | str) -> list[ChainEntry]:
    if isinstance(items, str):
        items = [p.strip() for p in items.split(",") if p.strip()]
    out: list[ChainEntry] = []
    for item in items:
        entry = parse_chain_entry(item) if isinstance(item, str) else None
        if entry:
            out.append(entry)
    return out


def _legacy_local_entry() -> ChainEntry:
    s = get_settings()
    return ChainEntry(
        provider=_normalize_provider(s.llm_provider),
        model=s.ollama_model.strip(),
        base_url=s.ollama_url.strip().rstrip("/"),
    )


def _default_tiers_from_env() -> dict[str, list[ChainEntry]]:
    s = get_settings()
    local = _legacy_local_entry()
    light_raw = s.llm_tier_light.strip()
    medium_raw = s.llm_tier_medium.strip()
    heavy_raw = s.llm_tier_heavy.strip()

    light = _parse_chain_list(light_raw) if light_raw else [local]
    medium = _parse_chain_list(medium_raw) if medium_raw else [
        ChainEntry(provider="gemini", model="gemini-2.0-flash"),
        local,
        ChainEntry(provider="ollama", model=s.ollama_model.strip(), base_url=s.ollama_url.strip().rstrip("/")),
    ]
    heavy = _parse_chain_list(heavy_raw) if heavy_raw else [
        ChainEntry(provider="gemini", model="gemini-2.5-pro"),
        ChainEntry(
            provider="openai",
            model="claude-3-5-sonnet-20241022",
            base_url="https://api.anthropic.com/v1",
        ),
        local,
    ]
    return {"light": light, "medium": medium, "heavy": heavy}


def _tiers_file_mtime() -> float:
    try:
        return LLM_TIERS_PATH.stat().st_mtime if LLM_TIERS_PATH.is_file() else 0.0
    except OSError:
        return 0.0


@lru_cache
def _load_tier_chains_cached(_mtime: float) -> dict[str, list[ChainEntry]]:
    if LLM_TIERS_PATH.is_file():
        try:
            raw = json.loads(LLM_TIERS_PATH.read_text(encoding="utf-8"))
            tiers: dict[str, list[ChainEntry]] = {}
            for name in VALID_TIERS:
                entries = _parse_chain_list(raw.get(name, []))
                if entries:
                    tiers[name] = entries
            if tiers:
                return {name: tiers.get(name, _default_tiers_from_env()[name]) for name in VALID_TIERS}
        except (json.JSONDecodeError, OSError) as exc:
            log.warning("Could not load %s: %s", LLM_TIERS_PATH, exc)
    return _default_tiers_from_env()


def load_tier_chains() -> dict[str, list[ChainEntry]]:
    """Reload when data/llm_tiers.json changes (mtime busts the cache)."""
    return _load_tier_chains_cached(_tiers_file_mtime())


def get_chain(tier: str) -> list[ChainEntry]:
    chains = load_tier_chains()
    key = tier.strip().lower()
    if key not in chains:
        key = get_settings().llm_default_tier.strip().lower() or "medium"
    return list(chains.get(key, chains["medium"]))


def chain_to_dicts(chain: list[ChainEntry]) -> list[dict]:
    return [
        {
            "provider": e.provider,
            "model": e.model,
            "base_url": e.base_url,
        }
        for e in chain
    ]
