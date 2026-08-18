# Recovery → Daily Capacity Hint — Implementation Plan

**Goal:** Whoop/RescueTime-inspired hint: watch **sleep score** adjusts suggested focus hours for the day.

**Architecture:** Pure `recovery_hint.py` from sleep_score / sleep_hours. Attached to `day_status` wearables snapshot and hub daily. UI in `ProductivityGoalsPanel` capacity box.

---

### Task 1: Hint function

**Files:**
- Create: `backend/behavior/recovery_hint.py`

**Rules:**

| sleep_score | factor | label |
|-------------|--------|-------|
| ≥ 85 | 1.0 | Full capacity |
| 70–84 | 0.9 | Good recovery |
| 55–69 | 0.75 | Moderate — trim deep work |
| 1–54 | 0.6 | Low recovery — lighter day |
| missing, sleep < 6h | 0.7 | Short sleep |

`suggested_focus_hours = round(base_focus_hours * factor, 1)`

- [ ] `compute_recovery_hint(sleep_score, sleep_hours, base_focus_hours=4.0)`

### Task 2: Wire APIs

**Files:**
- Modify: `backend/behavior/day_status.py` — `_wearables_snapshot()` adds `recovery_hint`
- Modify: `backend/hub/router.py` — daily payload includes hint when wearables present

### Task 3: UI

**Files:**
- Modify: `ProductivityGoalsPanel.tsx` — optional `sleepScore` prop, show suggested hours in capacity box
- Modify: `ProductivityPage.tsx` — pass sleepScore to goals panel

### Task 4: Tests

- Create: `tests/test_recovery_hint.py`

**Verify:** pytest + build
