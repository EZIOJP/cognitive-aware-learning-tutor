# Gate single source of truth — desktop · extension · web

**Date:** 2026-09-04  
**Choice:** Full single source (user option 1)

## Decision

| Surface | Owns | Does not own |
|---------|------|----------------|
| **Python** `browser_gate_policy` + `distraction_gate` | Modes, allow/watch/porn/social/keywords, `force_*` hosts, `content_score`, morning `allow_paths` / `redirect_url`, hard-block exes | SoftLand chrome APIs |
| **Extensions** | Enforce SoftLand/DNR from live `browser` payload; offline seeds **generated** from Python | Authoring domain lists by hand |
| **Web SPA** | Soft-redirect using `morning.allow_paths` + `morning.redirect_url` | Hardcoded study/plan path trees |
| **Desktop tracker** | Kill games / hard-block exes via `should_hard_block` | Site SoftLand (extension only) |

## Live payload → extension

- **SoftLand / classify:** `browserPolicyOrFallback(gateCache.browser)` — lists + flags from API.
- **DNR watch/porn:** `dnrHostList(force_*, domains)` from the same payload (cap 16 / 40); SoftLand skips **only** hosts in `activeDnr*Hosts` so overflow still SoftLands.
- **Offline:** generated `FORCE_*` / `FALLBACK_*` / `CONTENT_SCORE_*` in `gate_policy.js` via `scripts/sync_gate_policy_seeds.py`.

## Implementation

1. `scripts/sync_gate_policy_seeds.py` — domain seeds + content-score weights; `build_extension_workers.ps1` bundles SWs.
2. `MorningGateRedirect` — if `next !== open` and path not allowed → `navigate(redirect_url)`.
3. Extensions apply `browser.intervals.extension_gate_poll_s` (**300s / 5 min** heartbeat); **`/ws/gate` GATE_CHANGED** forces immediate fresh GET on rule/morning changes.
4. Keep gate TTL caches + singleflight; invalidate on mutations.

## Non-goals

- Merging SelfTracker and calt-gate into one package
- Desktop SoftLand
- Changing hard-block exe lists (already Python-only)
- Device OS porn mega-list (`device_block`) — separate from extension DNR
