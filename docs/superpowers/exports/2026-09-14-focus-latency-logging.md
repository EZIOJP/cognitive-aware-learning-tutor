# Focus slowness — latency logging shipped (2026-09-14)

## Why it feels slow (primary)

Enforcer commands are **serialized on one named pipe**. Home (15s), Settings Unlock/FocusControl (12s), WriteGate (15s), Bedtime (8s) all call `enforcerNativeCmd`. When several overlap, later calls **wait in queue** — UI looks frozen even if each pipe round-trip is fast.

Secondary: large `dist-focus` JS (~5.6MB), SoftLand/data mirror fetches, enforcer wedge/timeouts.

## What we added

| Piece | Role |
|-------|------|
| `src/lib/focusPerfLog.ts` | Ring buffer; thresholds warn 500 / high 1500 / critical 3000 ms; **review filter** = high+ or any error |
| `enforcerNativeCmd` instrumentation | Logs queue wait + round-trip + total; coalesce duplicate status probes; log `queue_dropped` / `coalesced` / `timeout` |
| `timedFocusFetch` on day_rollup + enforcer_status mirrors | Data-plane latency |
| **Settings → Tools → Perf review** | Filtered table + p50/p95 + Copy review JSON |

Console: `[FocusPerf high|critical|error] …` for review-worthy events.

## How to use

1. Tray Reload UI / restarted Focus (already rebuilt).
2. Use Home + Settings for ~1–2 minutes.
3. Open **Settings → Tools** → **Perf review**.
4. Copy review JSON if you want to paste back for analysis.

## Next speed fixes (after samples)

- Prefer mirrors over pipe for read-only chips (already partial).
- Raise poll intervals / share one poll bus.
- Keep enforcer service installed so pipe never wedges.
