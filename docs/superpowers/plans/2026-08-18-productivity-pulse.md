# Productivity Pulse — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:executing-plans`

**Goal:** RescueTime-style **Productivity Pulse** (0–100) on desktop stats and GlanceBar.

**Architecture:** Pure function maps each session’s productivity score to five level weights, time-averages them, and attaches productive/distracting second totals. No new DB tables.

**Tech stack:** Python (`productivity_pulse.py`), existing `stats_aggregate` buckets, FastAPI `desktop-stats`, React `GlanceBar`.

---

### Task 1: Pulse computation module

**Files:**
- Create: `backend/behavior/productivity_pulse.py`
- Modify: `backend/behavior/router.py` (`_desktop_stats_from_tracked_sessions`)

**Level weights (RescueTime-aligned):**

| Score band | Label | Weight |
|------------|-------|--------|
| 80–100 | Very productive | 100 |
| 60–79 | Productive | 75 |
| 40–59 | Neutral | 50 |
| 20–39 | Distracting | 25 |
| 0–19 | Very distracting | 0 |

- [ ] Add `level_weight(score)`, `compute_pulse_from_sessions(sessions)`, `pulse_label(pulse)`
- [ ] Merge pulse fields into desktop-stats payload: `pulse`, `pulse_label`, `productive_seconds`, `distracting_seconds`
- [ ] Keep `avg_productivity_score` for backward compatibility

### Task 2: Frontend GlanceBar

**Files:**
- Modify: `src/api/behaviorClient.ts` — extend `DesktopStats`
- Modify: `src/components/productivity/GlanceBar.tsx` — show Pulse ring (prefer pulse over raw avg when present)

- [ ] Display pulse 0–100 with label “Pulse · {rangeLabel}”
- [ ] Tooltip/subtitle when pulse differs from avg score

### Task 3: Tests

**Files:**
- Create: `tests/test_productivity_pulse.py`

- [ ] Unit tests for level weights and mixed session list
- [ ] API test: desktop-stats includes pulse keys

**Verify:** `pytest tests/test_productivity_pulse.py` · `npm run build`
