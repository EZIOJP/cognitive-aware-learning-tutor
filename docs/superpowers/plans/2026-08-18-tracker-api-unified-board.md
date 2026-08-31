# Tracker API unified board — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:executing-plans`

**Goal:** One day-status payload for Android, hub alias, and web Life Tracker — includes pulse, goals, focus quality, recovery, weekly snippet, study-mode nudge.

**Source:** Competitive sprint handoff — mobile/watch clients lagged behind web productivity APIs.

---

## Tasks

### 1. Backend productivity snapshot
- [x] `backend/behavior/day_productivity.py` — `build_productivity_snapshot()`
- [x] Extend `build_day_status()` → `schema: 3`, `productivity` block
- [x] Hub `/api/hub/day-status` inherits via same builder

### 2. ActivityWatch export (P2)
- [x] `backend/behavior/activitywatch_export.py`
- [x] `GET /api/behavior/export/activitywatch?day=`

### 3. Clients
- [x] `packages/calt-android-tracker/lib/api.ts` — DayStatus types
- [x] `packages/calt-android-tracker/app/index.tsx` — pulse / goal / focus cards
- [x] `src/api/behaviorClient.ts` — `fetchDayStatus`, `fetchActivityWatchExport`
- [x] `src/components/life/TrackerDayBoard.tsx` — Life Tracker board

### 4. Tests + verify
- [x] `tests/test_day_productivity.py`
- [x] Extend `tests/test_day_status.py` (schema 3)
- [ ] Full pytest + `npm run build`

### 5. Docs
- [ ] `docs/SESSION_LOG.md`, `docs/PROJECT_STATUS.md`
- [ ] Mark item 15 partial in competitive priority matrix

---

## Payload shape (`productivity`)

```json
{
  "pulse": 62,
  "pulse_label": "Productive",
  "goal_pct": 45,
  "goal_met": false,
  "focus_quality": { "score": 78, "label": "Solid focus", "switches": 4 },
  "weekly": { "avg_pulse": 58, "goal_met_days": 4 },
  "alerts": [{ "id": "youtube_cap_30m", "triggered": true }],
  "study_mode_nudge": { "active": false }
}
```

Wearables `recovery_hint` stays under `wearables` (unchanged).

---

## Out of scope

- Health Connect reader, auto roll-forward blocks, Reclaim focus defense, Rize auto-detect (P2 backlog)
- Zepp mini-program UI (does not consume day-status today)
