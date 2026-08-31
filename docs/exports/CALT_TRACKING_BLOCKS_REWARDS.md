# CALT — Tracking, Blocking, Rewards (how it works)

**Exported:** 2026-08-19  
**Audience:** Owner review — one file for *how time is counted, how distraction is blocked, and how rewards unlock the day*.

**Copies:**

- Repo: `docs/exports/CALT_TRACKING_BLOCKS_REWARDS.md`
- Desktop: `C:\Users\Lenovo\Desktop\CALT_TRACKING_BLOCKS_REWARDS.md`

---

## Status of this product vs next OS

| Layer | Status |
|-------|--------|
| **PC tracking** (desktop + Edge sessions) | **Shipped** |
| **PC blocking** (games hard-kill + Edge gate + porn) | **Shipped** |
| **PC rewards** (Bible +10, Plan +10, day unlimited) | **Shipped** |
| **Watch** (health dump only) | **Shipped** — not a blocker |
| **Android Device Gate** (Flutter + native overlay) | **NEXT PLAN — not built** |
| **iOS / iPad Device Gate** | **NEXT PLAN after Android — not built** |

Android and iOS do **not** participate in tracking, blocking, or rewards yet. The Expo phone app only **shows** `day-status`. The next product is a phone lock that **obeys** the PC clock.

Specs: `docs/superpowers/specs/2026-08-19-mobile-device-gate-design.md`  
Plan: `docs/superpowers/plans/2026-08-19-mobile-device-gate.md`

---

## 1. The whole loop (one day)

```text
TRACK  →  SCORE  →  REWARD STEPS  →  UNLOCK  →  STOP BLOCKING
 (who)     (what counts)  (Bible/Plan +10)   (day_unlimited)   (games + sites)
```

**Morning (SPA + Edge):** Bible chapter → confirm plan.  
**All day (PC):** productive minutes (apps + Edge) vs daily goal (~240).  
**Unlock games / normal browse:** study goal **and** ≥1 Bible chapter today (or day-pass / earned reward-day).  
**Porn:** blocked whenever the gate is armed or morning is still locked — not a “reward.”

Disable morning SPA redirect with `MORNING_GATE=0` (rewards can still grant if you complete the steps).

---

## 2. Tracking (who writes time)

All lasting “actual” minutes land in SQLite **`tracked_sessions`**.

| `source` | Collector | What is timed |
|----------|-----------|----------------|
| `desktop_tracker` | Windows tray tracker | Foreground **exe** + window title. **Ignores Edge** (browser owned by extension). |
| `extension` | Edge SelfTracker | Focused tab **URL / domain / title**. Skips localhost CALT. |
| `calt_spa` | Web app heartbeat | Only productive lanes: lecture notes (reading), `/review`, GRE, math. **Not** Bible as study minutes. |

**How a session ends:** app/tab switch, idle (~5 min desktop), max slice (~2–10 min depending on config), flush.

**Scoring:** category map + policy; score ≥ **threshold ~60** = productive. Overlapping desktop+Edge intervals are **unioned** so you are not double-paid. **Watch sleep** subtracts “Cursor at 3am.”

**Not the goal clock:** SelfTracker telemetry JSONL, content-script scroll stats, Gate extension (no sessions).

**APIs / files:** `backend/behavior/tracker_service.py`, `selftracker-extension/`, `backend/behavior/study_presence.py`, `GET /api/behavior/desktop-timeline`, week export `GET /api/planner/export/last-7-days`.

---

## 3. Blocking (who stops distraction)

Two **different** machines, one **policy**:

### A) Windows games / exes (hard-block)

- Toggle: `hard_block_enabled` on productivity policy.  
- Tracker poll: if day **locked** and foreground exe is Gaming / `hard_block_exes` → **kill PID**.  
- Protect: explorer, Cursor, tracker, etc.  
- Soft-pause of tracker **ignored** while armed.

Code: `backend/behavior/distraction_gate.py` (`should_hard_block`), `tracker_service.py`.

### B) Edge sites (CALT Gate + SelfTracker policy)

Same JSON: `GET /api/behavior/distraction-gate` → `browser.*`

| Mode | Typical |
|------|---------|
| `bible` | Soft-land to `/bible` |
| `planning` | Soft-land to `/productivity` |
| `study` | Allowlist study sites; other hosts blocked; watch/porn blocked |
| `free` / open | Watch may be allowed; **porn still forced block** when armed |

Layers: DNR host lists → URL/title keywords → **content-score** on visible text (soft warn then lock). Page HTML is **not** uploaded.

**TEMP_ALLOW:** short local bypass on the extension (existing Edge pattern). Phone 5‑min window is **next plan**, not this.

### C) Watch

Does **not** block apps. Dump only.

---

## 4. Rewards (what you earn)

**Not a game economy.** Two idempotent morning points per local day (`data/morning_rewards.json`):

| Award | Points | When |
|-------|--------|------|
| Bible | **+10** | Today’s chapter goal met (`chapters_completed` ≥ 1) |
| Plan | **+10** | `POST /api/behavior/morning-plan/confirm` after Bible |

Shown on gate as `morning.rewards`. Voice can praise. Demo clock **must not** write rewards.

**Bible vs games (current code, 2026-08):**

```text
day_unlimited =
    reward_day
    OR day_pass
    OR (productive_minutes >= daily_goal AND ≥1 chapter today)

unlocked (games) = (hard_block off) OR day_unlimited
```

Older “30 min PDF → 30 min game bank” is **legacy**; chapter + study goal is the primary unlock. `day_pass` does **not** skip morning Bible on the SPA.

**Spiritual vs productive:** Bible minutes/chapter = habit + unlock condition. GRE/notes/math/Cursor (scored) = productive minutes toward 240.

---

## 5. How it fits in one picture

```text
Edge SelfTracker ──┐
Desktop tracker  ──┼── tracked_sessions ── score ≥60 ── productive_minutes
CALT SPA study   ──┘         │
                             ▼
                    distraction-gate
                    ├── morning.next: bible | plan | open
                    ├── morning.rewards: +10/+10
                    ├── day_unlimited / remaining_minutes
                    └── browser_mode + porn/watch lists
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
        Kill games      Redirect Edge    day-status JSON
        (tracker)       (Gate ext)       (phone glance TODAY)
                                          │
                                          ▼
                               NEXT: Android overlay
                               THEN: iOS shields
```

**day-status** (`GET /api/behavior/day-status`, hub `:8765`): checklist, `hard_block.*`, tracker alive, wearables. Phone **reads** this today. Phone **will enforce** it in the next plan.

---

## 6. Source docs (if you want the originals)

| Topic | File |
|-------|------|
| Minutes + calendar | `docs/PRODUCTIVITY_SYSTEM.md` |
| Game hard-block | `docs/superpowers/specs/2026-07-17-distraction-hard-block-design.md` |
| Bible + unlimited | `docs/superpowers/specs/2026-07-22-bible-reader-game-gate-design.md` |
| Morning +10/+10 | `docs/superpowers/specs/2026-08-04-morning-unlock-rewards-design.md` |
| Page content score | `docs/superpowers/specs/2026-08-11-content-score-distraction-gate-design.md` |
| Phone glance | `docs/superpowers/specs/2026-08-04-amazfit-android-tracker-bridge-design.md` |
| Watch dump | `docs/CALT_SYNC_MANUAL_DUMP.md` |
| **Next OS** | `docs/superpowers/specs/2026-08-19-mobile-device-gate-design.md` |
| **Next OS plan** | `docs/superpowers/plans/2026-08-19-mobile-device-gate.md` |
| Wider review | `docs/exports/CALT_PROJECT_TRACKERS_DEVICE_GATE_REVIEW.md` |

Code: `backend/behavior/distraction_gate.py`, `backend/planner/morning_rewards.py`, `backend/behavior/browser_gate_policy.py`.

---

## 7. NEXT PLAN — Android then iOS (not started)

**Goal:** Same rule on the phone: **no distraction until PC `day_unlimited` / gate unlocked.** Porn always hard. After unlock, optional **5‑minute** rest on non-porn apps.

| Phase | OS | What | Status |
|-------|-----|------|--------|
| 0 | PC | Add `device_gate.unlocked` on `day-status` (same boolean as now) | **NEXT** |
| 1 | Flutter | UI: minutes left, poll PC, fail closed offline | **NEXT** |
| 2 | **Android** | Kotlin Accessibility overlay + UsageStats | **NEXT PLAN (v1)** |
| 3 | Android | Optional DNS/VPN porn backstop | **NEXT** |
| 4 | **iOS / iPad** | Family Controls + DNS; weaker than Android | **NEXT PLAN after v1** |

**Will not be in v1:** phone-generated productive minutes, Flutter-only blocking, Play/App Store, watch as enforcer.

---

## 8. One-sentence summary

On the PC, CALT **tracks** apps and Edge tabs, **blocks** games and sites until Bible + plan + productive goal (with +10/+10 morning points), and **does not** yet lock Android or iOS — those are the **next plan**, Android first.
