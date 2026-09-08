# Gate async scheduler — 5‑minute heartbeat + fresh rules on change

**Date:** 2026-09-04  
**Choice:** A+B+C hybrid (event-driven server + client leader + slow poll backup)

## Problem

Chatty ~4s pings from SPA tabs + SelfTracker + calt-gate stampede `compute_distraction_gate` / SQLite.

## Decision

| Layer | Behavior |
|-------|----------|
| **Baseline ping** | **5 minutes** (`extension_gate_poll_s: 300`) — health / drift backup only |
| **Fresh rules** | On any policy/morning/free-override/device-block mutation → **invalidate cache** + bump `policy_gen` + **WS `GATE_CHANGED`** → extensions/SPA **immediate** GET |
| **Singleflight** | Concurrent GETs coalesce to one compute per user |
| **SPA** | One BroadcastChannel leader; pause when `document.hidden`; 5 min backup |
| **Failure** | Exponential backoff on fetch error (still fail-closed SoftLand/DNR) |

## Why not “only 5 min poll”

Without push/invalidate, bible confirm / Free time / rules toggle would lag up to 5 minutes. That is unacceptable. **Heartbeat is slow; freshness is event-driven.**

## Non-goals

- Replacing SoftLand/DNR enforcement path
- Merging the two extensions
- Changing desktop kill logic
