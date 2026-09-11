# Focus standalone — progress (2026-09-11)

## Landed

| Phase | Status |
|-------|--------|
| 0 Door | Study interstitial; Open Study |
| 1 Live Settings | Hub + EnforcerWriteGate |
| 2 P5a | Unlock accounting smoke green |
| 3 P5b core | `classify_rules.json` + enforcer `day_rollup.json` + reason aliases |
| **P5c** | Python `distraction_gate` / `goals_alerts` read `day_rollup.json` when fresh |
| 4 P6 track | SelfTracker WS/HTTP **opt-in** (default off); `selftracker` in stats filters |
| 5 Dataplane | Focus reads `day_rollup` / `enforcer_status` mirrors |
| **6a Planner** | Enforcer owns `planner_blocks` / `planner_routines`; gateway CRUD; Focus Plan UI via pipe |
| **6b Plan→SoftLand** | Tick + `plan.apply_gate`: free/break → `free_until`; study → clear plan free; `runtime.plan_block` |
| **Planner restore** | Focus offline again: `plan.start` / `complete` / `roll_forward` / `overlay` / `adherence` / `routine.apply` |
| **7 Standalone** | No Focus auto-start `:8000`; Gate SoftLand = **native only** (HTTP fallback deleted); Focus soft-fails Study-only planner ops |
| **UX polish** | Design host `:5180` (`npm run dev:focus`); Calendar active/next plan-block cards; Goals SoftLand lists |
| **Bible+Journal → Focus** | Enforcer `journal.*` / `bible.*` gateway; Focus nav; Study interstitial; SoftLand `bible_done` native |

Binaries: rebuild/restart `calt_enforcer` + `calt_focus`; `npm run build:focus`.

### Focus design host

```bat
npm run dev:focus
:: http://127.0.0.1:5180/  — hot-reload Focus UI; mirrors via /calt-data/
```

Writes (SoftLand/Arm/Plan mutations) need `calt_focus.exe` + enforcer pipe.

### Productivity without Study `:8000`

Works: SoftLand, Arm, site rules, schedules, day-pass/spend, Plan CRUD + start/complete/roll-forward + apply routines, Calendar glance/overlay/adherence from enforcer, browser SoftLand via msg_host, OS kills.

Still need sidecar / Study API when you use them:
- Google Calendar OAuth (`:8000` planner routes)
- Wearables hub `:8765`
- LLM propose / generate-from-timetable / seed-default-routines
- Study content (GRE, Bible pages, Notes)

### Smokes

```bat
powershell -File scripts\desktop_tracker\run\smoke_plan_6a.ps1 -Mutate
powershell -File scripts\desktop_tracker\run\smoke_plan_6b.ps1
powershell -File scripts\desktop_tracker\run\smoke_plan_restore.ps1
powershell -File scripts\desktop_tracker\run\smoke_p5a.ps1
```

## Optional later

| Item | Notes |
|------|--------|
| **3b** | Native LLM propose / classification-review (shrinks sidecar) |

## Verify (owner)

1. Kill Study `:8000` — SoftLand/Arm/Settings/Plan CRUD/Calendar glance still work in Focus.
2. Reload Gate — SoftLand never hits `:8000` for get_mode.
3. Tray Start API only when you want Study content / Google / propose.
