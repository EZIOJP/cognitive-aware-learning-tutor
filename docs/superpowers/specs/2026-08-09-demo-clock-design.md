# Demo clock (read-only time travel) — 2026-08-09

**Status:** Implemented  
**Goal:** Demo Soft-land / browser modes by scrubbing wall time against **real** day data.

## Locked choices

| Choice | Decision |
|--------|----------|
| Fake productive minutes | **No** |
| Inject / populate fake sessions | **No** |
| Demo writes (confirm, auto-plan, rewards, bible day JSON) | **Blocked** while demo on |
| Data source | Real planner blocks + tracked sessions for the demo calendar day |
| October sample | Not in this DB — UI lists real days (e.g. 2026-08-04, 2026-07-04) |

## Behavior

- `data/demo_clock.json` stores `{enabled, now_iso}` only.
- Gate / bible day key / plan window / free-after use `demo_clock.now_local()`.
- Productive minutes = real tracked score for that day (unchanged formula).
- UI: Productivity → Settings → Demo mode + amber banner when on.

**Safety:** Bible `_day_key()` always uses **real** wall clock (never demo). Demo must not reset reading progress.

## Future (not this)

- Tagged Daily Practice engine: [docs/FUTURE_TAGGED_DAILY_PRACTICE.md](../../FUTURE_TAGGED_DAILY_PRACTICE.md)
