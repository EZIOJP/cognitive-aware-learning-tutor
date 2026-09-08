# Morning status — overnight polish (2026-09-07)

## Done (agent)

| Priority | Result |
|----------|--------|
| 1 Zero-Python tracker | Verified: reads `enforcer_policy.json`, writes `enforcer_status.json` (~2.5s), kills when armed+locked, skips browsers, ownership lock. Smoke: status file written with `owns:true`. |
| 2 Broad browsers | Native `IsBrowserExe` + `browser_labels` + SelfTracker UA + `tracker_ignore` (all browsers desktop-ignored; extension kept). |
| 3 Anti-tamper | Taskmgr, Process Explorer/Hacker, resmon/perfmon, w32tm, tzutil while locked. |
| 4 Focus UI | Armed/owns/lock badges; last kill; Arm/Disarm → policy JSON; lock modes; anti-tamper toggle. |
| 5 Extensions + stats | SelfTracker `msedge.exe` + tab fields; desktop ignore prevents bare browser double-count. |
| 6 Run/install | Console + Admin service + Task Scheduler (native required); scripts README + INSTALLER + morning smoke doc. |
| 7 Sweep | Legacy Python enforcer marked; docs/reminder/AGENTS aligned; tests green. |

Natives rebuilt: `calt_enforcer.exe`, `calt_msg_host.exe`.

## Still needs you (Admin / UI)

See **[2026-09-07-owner-tasks.md](./2026-09-07-owner-tasks.md)** for the checkbox list.

1. **Optional stay-alive:**  
   `powershell -ExecutionPolicy Bypass -File scripts\desktop_tracker\install_native_enforcer.ps1`
2. **Reload** SelfTracker + CALT Gate in `edge://extensions`
3. **Human smoke** (Notepad kill + Edge site in stats) — see below

## Exact smoke commands

```bat
run.bat
scripts\desktop_tracker\run_native_enforcer_console.bat
```

Then:

1. http://127.0.0.1:5173/productivity/focus → Arm `notepad.exe` → open Notepad → dies  
2. Optional: `taskkill /F /IM python.exe /T` → Notepad still dies  
3. Edge browse → `/productivity` shows **Microsoft Edge** + site  

Full checklist: [2026-09-07-morning-smoke.md](./2026-09-07-morning-smoke.md)

## Follow-ups from zero-Python audit (2026-09-07)

| Item | Status |
|------|--------|
| Python TrackerService kills when lock stale | **Fixed** — `enforcer_owns_kills()` defaults True; only `CALT_UI_KILLS=1` re-enables |
| Task Scheduler Python fallback | **Fixed** — requires `-AllowPythonFallback` |
| Stale SQLite exes when JSON `exes: []` | **Fixed** — JSON always replaces exes |
| Dual Arm copy (Productivity vs Focus) | **Clarified** — Productivity = SoftLand/game bank; Focus Enforcer = OS kills |
| Category backfill (F2) | **Parked** — native sessions keep `category_source=native`; no Focus backfill |
| Admin service install | **Owner** — `install_native_enforcer.ps1` |
| Audit follow-up verified | **2026-09-07 morning** — 8 tests pass; `calt_enforcer.exe` rebuilt |
