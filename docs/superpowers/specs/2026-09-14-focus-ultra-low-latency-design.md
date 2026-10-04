# Focus ultra-low-latency control plane

**Date:** 2026-09-14  
**Owner ask:** A + B + C + anything more powerful — app must feel fast; OK with extra local helpers (not Redis/Docker for SoftLand truth).

## Problem

Many Focus panels independently poll `enforcerNativeCmd` on a **single serialized named pipe**. Queue wait dominates latency. Redis/Docker do not fix a local single-writer SoftLand brain.

## Layers (ship in order)

| Phase | Name | What | Latency effect | Status |
|-------|------|------|----------------|--------|
| **A** | FE status bus | One poller; subscribers; mirror-first; pipe only when mirror stale / writes | Large, immediate | **Done** (`focusStatusBus` + Home/WriteGate/FocusControl/Bedtime) |
| **B** | Local status sidecar | Optional tiny helper = sole status pipe client; FE HTTP/WS parallel reads | Larger for multi-tab / many panels | **Scaffold** — `scripts/desktop_tracker/run/calt_status_sidecar.py` (`:18765/snapshot`); bus already probes |
| **C** | Enforcer → WebView push | C++ posts `status_tick` / softland snapshot on interval | Best steady-state | **Done in Focus shell** — `PushStatusTick` every tip timer (~2.5s); FE `installFocusStatusPushListener` |
| **D** | Hot mirrors (more powerful) | Enforcer writes `enforcer_status.json` + softland/day_rollup every tick; bus never touches pipe for chips | Near-zero read latency | **Partial** — mirrors already; bus prefers them; pipe ≈ 24s reconcile |

**Rejected for SoftLand truth:** Redis, Docker FE container as production path (dev:focus Vite OK for edit speed only).

## Phase A design (implement now)

```text
focusStatusBus
  ├─ tick every ~4s (visible only): mirrors first
  ├─ softland_policy.json, enforcer_status.json, day_rollup.json
  ├─ optional day.loop_snapshot via pipe at most 1× / tick if bridge up AND mirror age > 20s
  └─ subscribers: HomeModeBoard, EnforcerWriteGate, FocusControlPanel, BedtimeOverlay, …
```

- Writes (`arm.set`, SoftLand patch, etc.) still call `enforcerNativeCmd` directly.
- After successful write, bus `invalidate()` for immediate refresh.
- Perf log already records queue waits — should drop after A.

## Phase B (next)

- `calt_status_sidecar` or Focus-internal thread: drain status ops; expose `http://127.0.0.1:18765/status`.
- FE bus prefers sidecar when reachable; else mirrors; else pipe.
- Stay-alive with enforcer install.

## Phase C (after B)

- `calt_focus` WebView: on enforcer tick callback / Focus timer reading pipe once, `PostWebMessageAsJson({type:"status_tick",...})`.
- Bus listens; disables interval when push healthy.

## Phase D

- Ensure enforcer publishes mirrors every tick (status already); softland mirror on SoftLand tick.
- Bus default = mirrors only; pipe reserved for mutations + rare reconcile.

## Success metrics (Tools → Perf review)

- p95 enforcer_cmd latency ↓  
- `queue_dropped` / `coalesced` rare  
- UI chips update without Settings freeze  

## Non-goals

- Moving SoftLand decide to Redis/HTTP Study `:8000`
- Requiring Docker for daily Focus use
