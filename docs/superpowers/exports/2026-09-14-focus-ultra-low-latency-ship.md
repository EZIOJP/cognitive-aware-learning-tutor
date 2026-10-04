# Focus ultra-low-latency — ship note (2026-09-14)

## What landed

| Phase | Deliverable |
|-------|-------------|
| **A** | `src/lib/focusStatusBus.ts` + `useFocusStatus` — one ~4s ticker; Home / WriteGate / FocusControl / Bedtime subscribe; writes invalidate |
| **B** | Optional `python scripts/desktop_tracker/run/calt_status_sidecar.py` → `http://127.0.0.1:18765/snapshot` (bus already probes) |
| **C** | `calt_focus` `PushStatusTick` posts `{type:"status_tick",…}` ~2.5s; App installs `installFocusStatusPushListener` |
| **D** | Bus prefers mirrors; pipe reconcile ≤1×/24s |

## Feel it

1. `npm run build:focus` (done this session)
2. Rebuild + restart `calt_focus` (Phase C push)
3. Optional: start sidecar in a terminal
4. Settings → Tools → **Perf review** — expect fewer high `enforcer_cmd` queue waits

## Not done / optional next

- Wire more panels (GlanceBar, SoftLand lists) onto the bus
- Enforcer softland mirror every SoftLand tick if any lag remains
- Sidecar auto-start from Focus tray (not required for A/C)
