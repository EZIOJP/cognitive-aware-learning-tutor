# Productivity Settings + Focus merge — design

**Date:** 2026-09-07  
**Status:** Owner-approved (2026-09-07) — implement P0  
**Related:** [2026-09-06-calt-native-enforcer-design.md](./2026-09-06-calt-native-enforcer-design.md), [AGENTS.md](../../../AGENTS.md)  
**Plan:** [../plans/2026-09-07-productivity-settings-focus-merge.md](../plans/2026-09-07-productivity-settings-focus-merge.md)

## Goal

One Productivity **Settings** hub that contains everything today split across:

- `/productivity?tab=settings`
- `/productivity/focus` (`FocusControlPanel`)
- orphan panels not mounted anywhere (`ProductivityPolicyPanel`, `WearablesSyncPanel`)

Keep **Approach A**: Settings is the hub; `/productivity/focus` stays as a deep link to the **same** Focus panel component (no duplicate UI). No Qt expansion. No Python kill path. Native `calt_enforcer` still owns OS kills.

## Owner clarifications (locked)

1. **SoftLand vs Arm callout (required)** — permanent note at top of Settings:
   - SoftLand = sites in Edge (Gate)
   - Arm Enforcer = OS process kills (`calt_enforcer`)
   - SoftLand ON does **not** kill Steam. Arm does **not** SoftLand sites by itself.
2. **Tray / deep link**
   - `calt_focus` / tray “Open Focus” → `/productivity/focus` (keep)
   - Optional later (P1): tray “Open Settings” → `/productivity?tab=settings#focus`
   - Do **not** force tray into full Settings scroll in P0

### Naming (SoftLand vs armed) — lock before P0

| Name | Meaning | Where |
|------|---------|--------|
| `softland_enabled` (preferred API/UI) | SoftLand / game-bank — **no OS kills** | Maps to DB column `hard_block_enabled` (legacy) |
| `hard_block_armed` | Native kill switch | `enforcer_policy.json` only |

- P0: dual-read/write API alias `softland_enabled` ↔ `hard_block_enabled`; UI never labels SoftLand as “hard block”.
- Physical DB column rename → follow-up (wide migration); not required to ship Settings mount.
- First-boot seed of `enforcer_policy.json` must **never** set `hard_block_armed` from SoftLand.

### Kill list while armed + locked

While `hard_block_armed` and an active lock (`lock_mode` timer/password/phrase still blocking Disarm), **kill-list writes are refused** (same gate as Disarm). UI disables the exe field. Prevents bypass by deleting `steam.exe` mid-lock.

### Rollback (P0)

If mounting orphans breaks Settings: revert the Settings-tab mounts/imports in `src/pages/ProductivityPage.tsx` (or git revert the P0 commit). Focus route stays independent.

## Rule of thumb (two brains)

| Concern | Runtime owner | Settings home | Data |
|--------|----------------|---------------|------|
| SoftLand (sites in Edge) | CALT Gate → FastAPI `:8000` | `#policy` + Planning (RO knobs) | SQLite + distraction gate |
| Hard block (process kills) | `calt_enforcer.exe` | `#focus` | `data/behavior/enforcer_policy.json` + `enforcer_status.json` |

SoftLand ON does **not** kill Steam. Arm Enforcer does **not** SoftLand sites by itself.

```text
You (Settings / Focus UI)
├── Python API :8000 — SoftLand + study compute
│   ├── distraction_gate / browser SoftLand mode
│   ├── productivity_policies (scores, SoftLand toggles)
│   ├── planner (routines, morning, reminders data)
│   └── tracked_sessions (overrides, export)
├── enforcer_policy.json — Arm / kill list / lock
│   └── calt_enforcer.exe → TerminateProcess
│       └── enforcer_status.json · ownership lock
└── Edge: CALT Gate + SelfTracker
    └── poll SoftLand · tab/domain stats → SQLite
```

## IA after merge

`/productivity?tab=settings` sections (top → bottom), with in-page anchors:

1. `#focus` — Focus / Enforcer (`FocusControlPanel`)
2. `#policy` — SoftLand / productivity policy (`ProductivityPolicyPanel`) — **mount orphan**
3. `#rules` — Blocking rules (`AppKillRulesPanel` + SoftLand site rules + gate schedules)
4. `#planning` — Planning (`PlanningSettingsPanel`)
5. `#demo-mode` — Demo mode (`DemoModePanel`) — already anchored
6. `#watch` — Watch ↔ PC (`WearablesSyncPanel`) — **mount orphan**, replace stub
7. `#reminders` — Plan reminders (`PlannerRemindersPanel`)
8. `#scoring` — Scoring & classification (override / activities / classification)
9. `#export` — Export data
10. `#setup` — Tracker setup (docs)

Replace “go to Focus” links with `#focus` / `#policy` / `#rules` where the intent is the same Settings tab.

`/productivity/focus` continues to render `FocusControlPanel` only (desktop shell / tray default).

---

## Per-setting architecture + use logic

### 1. Focus / Enforcer (`#focus`)

**Files:** `src/components/productivity/FocusControlPanel.tsx`, `src/pages/FocusPage.tsx`  
**APIs:** `GET /api/behavior/focus-dashboard`, `POST /api/behavior/focus-free-override`, `POST /api/behavior/focus-spend-earned`, arm/disarm writers → `enforcer_policy.json`

| Control | Architecture | Use logic |
|--------|--------------|-----------|
| SoftLand “Now” card | Gate snapshot: mode, morning.next, blocked, incubation, earned minutes | Glance why browsing is STUDY/FREE — not for OS kills |
| Free time (PIN) | SoftLand override until window ends | Temporary free browsing without Disarm |
| Spend earned | Burn banked minutes into free window | After productive bank; spend, don’t Disarm |
| Kill list (exes) | Written into policy JSON on Arm; native polls. **CRUD at `#rules`** (`AppKillRulesPanel`); Focus shows read-only chips + CTA | Apps to kill while armed |
| Lock mode / anti-tamper | Policy fields; native refuses Disarm until met | Stop casual Disarm / Task Manager while locked |
| Arm / Disarm | `hard_block_armed` + exes in JSON; status from `enforcer_status.json` | Turn OS kills on/off; needs healthy enforcer |

**Day use:** Arm when you need hard focus; Free/Spend for SoftLand relief; Disarm evening if unlocked.

### 2. SoftLand policy (`#policy`) — orphan → mount

**Files:** `src/components/productivity/ProductivityPolicyPanel.tsx`  
**APIs:** productivity policy CRUD, distraction-gate, Study Loop gate, Bible day-pass, reward day

| Control | Architecture | Use logic |
|--------|--------------|-----------|
| SoftLand on (game-bank) | `softland_enabled` (DB: `hard_block_enabled`) + gate; **not** OS kills | Keep SoftLand until study goal + Bible (or passes) |
| Study Loop required | `morning.study_loop_gate` | Force today’s quiz path before SoftLand relaxes |
| Bible day-pass | 2/week Mon–Sun | Skip Bible once; games until midnight |
| Reward / Free day | Bank from good days | Spend banked free day; tracking + adult filter stay on |
| Productive / blocked categories | Policy lists in SQLite | What counts toward goal; blocked never productive |
| Category scores + app overrides | Scorer inputs | Tune deep-work scoring; fix mislabeled apps |

**Day use:** Morning SoftLand commitment; day-pass/reward only when intentionally skipping ritual.

### 3. Planning (`#planning`)

**Files:** `src/components/productivity/PlanningSettingsPanel.tsx`, `planningPrefs` (localStorage)  
**APIs:** `autoApplyRoutinesToday`, `applyRoutines`, `GET distraction-gate` (read-only morning/browser)

| Control | Architecture | Use logic |
|--------|--------------|-----------|
| Auto-apply routines on sign-in | Client pref → once/day apply | Opt-in seed today’s blocks |
| Apply once / Force apply | Planner API | Manual or re-seed after routine edits |
| Morning gate knobs (RO) | `.env` → gate JSON | Understand lock reason; change via env, not UI |
| Browser daytime / `FREE_AFTER` | `browser_gate_policy` | After plan = study SoftLand; after evening hour = free |

### 4. Demo mode (`#demo-mode`)

**Files:** `src/components/productivity/DemoModePanel.tsx`  
**APIs:** demo clock

| Control | Architecture | Use logic |
|--------|--------------|-----------|
| Fake clock / presets | Overrides “now” for gate compute | Rehearse Bible → plan → STUDY → FREE without waiting |
| Jump to day | Calendar query + DAY view | See planner + gate under demo time |

### 5. Watch ↔ PC (`#watch`) — orphan → mount

**Files:** `src/components/productivity/WearablesSyncPanel.tsx`  
**APIs:** wearables ingest / queue / token

| Control | Architecture | Use logic |
|--------|--------------|-----------|
| Wearables sync | Phone/watch → PC → SQLite health | Test PC, then queue; token must match watch Settings |
| Stub today | Banner + link to Focus | Replace with real panel |

### 6. Plan reminders (`#reminders`)

**Files:** `src/components/productivity/PlannerRemindersPanel.tsx`  
**Storage:** localStorage + browser `Notification` API; polls today’s planner blocks

| Control | Architecture | Use logic |
|--------|--------------|-----------|
| Enable + lead minutes | Client-only notifications | Toast N minutes before next block |

### 7. Scoring & classification (`#scoring`)

**Files:** `SessionOverridePanel`, `ActivitiesPanel`, `ClassificationReview`

| Control | Architecture | Use logic |
|--------|--------------|-----------|
| Session override | PATCH one tracked session | Fix one wrong session |
| Activities | Day rollup from tracker | Diagnose what filled the day |
| Classification review | App→category mappings | Lasting scorer fixes (pairs with `#policy` overrides) |

### 8. Export (`#export`)

**Files:** inline on `ProductivityPage` Settings + `ExportRangeCalendar`  
**APIs:** week export JSON/CSV (also Propose context)

| Control | Architecture | Use logic |
|--------|--------------|-----------|
| Range, filters, sections | Export pipeline | Backup / analyze / feed AI propose |

### 9. Tracker setup (`#setup`)

Docs only: Edge SelfTracker + Gate load/reload; `run_calt_desktop.bat`, console smoke, `install_native_enforcer.ps1`. No live toggles.

---

## Day flow (recommended order)

1. Morning gate: Bible → confirm plan (env + Planning RO)  
2. SoftLand policy: goal / Study Loop / day-pass as needed  
3. Arm Enforcer if OS kills needed; Edge Gate for sites  
4. Free/Spend PIN only for temporary SoftLand relief  
5. Evening: Disarm (if unlocked); export / scoring review as needed  

---

## Implementation order (P0)

1. Mount `FocusControlPanel` at top of Settings (`#focus`)  
2. Keep `/productivity/focus` on the same component  
3. Mount `ProductivityPolicyPanel` (`#policy`)  
4. Mount `WearablesSyncPanel` under Watch (`#watch`)  
5. Add section anchors + intro SoftLand vs hard-block callout (once)  
6. Retarget “go to Focus” links to `#focus` / `#policy` when same-tab  

### P1 (polish)

- Accordion/collapse for Export / Setup / Scoring  
- GlanceBar enforcer strip → `#focus`  
- `calt_focus` tray: open `?tab=settings#focus`  

### P2 (new — after P0 live)

- Kill-list presets  
- Schedule preview (planner → SoftLand/hard-block windows)  
- Optional: drop Focus sidebar if Settings hub is enough  

## Out of scope

- Qt / PySide6 gate panels  
- New Python kill/track code  
- Second block database  
- Cold Turkey code  
- Rewriting Focus controls in C++  

## Source file map

| Surface | Path |
|--------|------|
| Settings host | `src/pages/ProductivityPage.tsx` (`tab === "settings"`) |
| Focus page | `src/pages/FocusPage.tsx` |
| Focus panel | `src/components/productivity/FocusControlPanel.tsx` |
| SoftLand policy | `src/components/productivity/ProductivityPolicyPanel.tsx` |
| Planning | `src/components/productivity/PlanningSettingsPanel.tsx` |
| Wearables | `src/components/productivity/WearablesSyncPanel.tsx` |
| Routes / nav | `src/plugins/productivity_plugin.tsx` |
| Native kills design | `docs/superpowers/specs/2026-09-06-calt-native-enforcer-design.md` |

## Success criteria

- All listed controls reachable from Settings without hunting Focus vs Settings  
- SoftLand vs hard-block labeled once and correctly  
- Orphans mounted and working behind API  
- `/productivity/focus` unchanged in behavior (shared component)  
- Enforcer still zero-Python at kill time  

---

**Owner:** review this file; say approve (or edit) before implementation plan.
