# Goals + Alerts v1 — Implementation Plan

**Goal:** RescueTime-style **daily goal progress** + **one-shot threshold alerts** (productive goal met, YouTube cap).

**Architecture:** `goals_alerts.py` evaluates today’s aggregated seconds against policy + defaults. Tracker poll (60s throttle) fires `enqueue_alert` once per day per alert id. Status exposed via API for UI.

---

### Task 1: Evaluation module

**Files:**
- Create: `backend/behavior/goals_alerts.py`
- Data: `data/behavior/goals_alert_state.json` (fired ids per day)

**Default alerts:**

| id | Type | Rule |
|----|------|------|
| `productive_daily_goal` | goal | productive_seconds ≥ policy.daily_goal_minutes × 60 |
| `youtube_cap_30m` | alert | youtube.com seconds ≥ 1800 |

- [ ] `evaluate_goals_alerts(db, user_id, day) -> list[AlertEvent]`
- [ ] `mark_fired(day, alert_id)` dedupe
- [ ] Custom message for goal met (no LLM)

### Task 2: Tracker hook + API

**Files:**
- Modify: `backend/behavior/tracker_service.py` — `_maybe_goals_alerts_if_due()` in `_poll_once`
- Modify: `backend/behavior/router.py` — `GET /api/behavior/goals-status?day=`

**Status payload:** goals with `current_seconds`, `target_seconds`, `pct`, `met`, alerts with `fired`.

### Task 3: Frontend (minimal)

**Files:**
- Modify: `src/api/behaviorClient.ts`
- Optional: small progress strip in GlanceBar or Goals panel

### Task 4: Tests

- Create: `tests/test_goals_alerts.py`

**Verify:** pytest
