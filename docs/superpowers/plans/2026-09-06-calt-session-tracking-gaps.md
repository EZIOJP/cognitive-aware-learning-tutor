# Session-tracking gaps (native C++) — 2026-09-06

**Legal:** Improved from CALT Python tracker patterns + Windows APIs.  
**Not** from Cold Turkey source/binaries (never copy CT files).

## Gaps found → fix status

| Gap | Risk | Fix |
|-----|------|-----|
| No idle cut | AFK time counted as app use | `GetLastInputInfo` → flush at 300s (same as Python) |
| No sleep gap | Hibernate adds hours to one session | Wall-clock jump >60s → close at last tick |
| No max chunk | Multi-hour single row | Cap 600s segments |
| FG fail ignored | Lock screen keeps old app open | Flush when FG unavailable |
| Browser tab sites | Only exe switch | Group `exe\|site` from title (light mirror of `session_key.py`) |
| Weak `session_id` | Rare collisions | `native-{endMs}-{pid}-{counter}` |
| SQLite lock fights | Dropped writes under load | `busy_timeout` + `WAL` |
| `category` NULL | Productivity undercount | Still open — Python classify later / follow-up |
| Stale ownership lock on kill -9 | Python thinks native owns | 30s stale; clean exit releases |
| Comms / Dashboard | Native rows need Desktop+API up for SoftLand | Unchanged by design |

## Still Python (intentional)

- Gate / SoftLand JSON (`distraction_gate` → `:8000`)
- Incubation / reward ledger
- LLM classification cache
- Study webapp
