# Competitive features — priority matrix

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` or `superpowers:subagent-driven-development`. Individual feature plans live alongside this file.

**Goal:** Borrow the highest-value competitor patterns into CALT with minimal scope — local-first, wire existing tracker/planner/wearables stack.

**Source:** [docs/COMPETITIVE_LANDSCAPE.md](../../COMPETITIVE_LANDSCAPE.md), [docs/COMPETITIVE_TECH_ARCHITECTURE.md](../../COMPETITIVE_TECH_ARCHITECTURE.md)

---

## Ranking (value × ease)

| Rank | Feature | Value | Ease | Plan | Status |
|------|---------|-------|------|------|--------|
| 1 | **Productivity Pulse** (RescueTime-style 0–100) | High | High | [2026-08-18-productivity-pulse.md](./2026-08-18-productivity-pulse.md) | **Done** |
| 2 | **Activities inbox** (ranked apps/sites + uncategorized) | High | Medium | [2026-08-18-activities-inbox.md](./2026-08-18-activities-inbox.md) | **Done** |
| 3 | **Goals + Alerts v1** (daily goal progress + threshold nudge) | High | Medium | [2026-08-18-goals-alerts.md](./2026-08-18-goals-alerts.md) | **Done** |
| 4 | **Recovery → capacity hint** (watch sleep → suggested focus) | Medium | Medium | [2026-08-18-recovery-capacity-hint.md](./2026-08-18-recovery-capacity-hint.md) | **Done** |
| 5 | **Shutdown ritual** (Sunsama-style end-of-day) | Medium | Medium | [2026-08-18-shutdown-ritual.md](./2026-08-18-shutdown-ritual.md) | **Done** |
| 6 | **Away-from-desk prompt** (idle return) | Medium | Low | [2026-08-18-away-prompt.md](./2026-08-18-away-prompt.md) | **Done** |
| 7 | **Overcommit warning** (plan > capacity) | Medium | High | `MorningAutoPlanPanel` + `planCapacityUtils.ts` | **Done** |

### P1 — completed this sprint
| # | Feature | Status |
|---|---------|--------|
| 8 | Weekly digest panel | **Done** |
| 9 | Recurring gate schedules | **Done** |
| 10 | Focus quality metric | **Done** |
| 11 | Alert → auto study mode nudge | **Done** |

---

## CALT constraints

- Reuse `tracked_sessions`, `stats_aggregate`, `productivity_policy`, `gate_alerts` — no second tracker.
- Pulse/alerts are **read-time** from existing rows; no new capture layer.
- Alerts speak via existing `enqueue_alert` → desktop tracker drain (canned or explicit message).
- Wearables hint reads `wearables_last_sync.json` / hub daily — no new hardware scope.
- Do not commit unless explicitly requested.

---

## Implementation order (completed)

1. Pulse on `GET /api/behavior/desktop-stats` + GlanceBar
2. `GET /api/behavior/activities` + Settings panel
3. Goals/alerts check in tracker poll + status API + GlanceBar goal %
4. Recovery hint on day-status + Goals panel
5. Shutdown ritual wizard + morning carry-forward banner
6. Away prompt on idle return (tracker Tk + `POST /api/behavior/away-response`)

Future backlog: weekly digest email, alert → auto study mode flip.
