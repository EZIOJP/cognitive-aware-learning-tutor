"""Probe configured LLM chains — run: PYTHONPATH=. python scripts/probe_llm_chains.py"""
from __future__ import annotations

from backend.config import get_settings
from backend.core.llm_capabilities import entry_is_configured, entry_to_options
from backend.core.llm_gateway import llm_complete
from backend.core.llm_probe import test_tier_chain
from backend.core.llm_routes import get_chain_for_tier


def main() -> None:
    s = get_settings()
    profile = s.llm_route_profile or "hybrid-free"
    print(f"PROFILE={profile}  tier_default={s.llm_default_tier}")
    print()

    for tier in ("light", "medium", "heavy"):
        chain = get_chain_for_tier(tier, route_profile=profile)
        print(f"=== {tier.upper()} chain ({len(chain)} entries) ===")
        for entry in chain:
            opts = entry_to_options(entry)
            cfg = entry_is_configured(entry)
            print(
                f"  {'[key OK]' if cfg else '[NO KEY]'} "
                f"{entry.provider}:{entry.model} -> {opts.base_url}"
            )
        r = test_tier_chain(tier, route_profile=profile)
        for e in r["entries"]:
            mark = "OK" if e.get("reachable") else "FAIL"
            print(f"    {mark} {e.get('entry')} {e.get('latency_ms')}ms {e.get('error') or ''}")
        print(f"  tier_reachable={r['reachable']}\n")

    print("=== LIVE coach (light) ===")
    res = llm_complete("Reply exactly: OK", task="coach", tier="light")
    print(f"  {res.provider}:{res.model} text={repr((res.text or '')[:60])} err={res.error}")


if __name__ == "__main__":
    main()
