# Morning smoke test — CALT Focus + zero-Python tracker

Run this when you wake up. Expect kills + Edge tab stats without Python owning the tracker.

## Prerequisites (once)

```bat
run.bat
scripts\desktop_tracker\build_native_enforcer.bat
```

Reload Edge extensions after JS changes: `edge://extensions` → SelfTracker + CALT Gate → Reload.

Optional stay-alive (Admin, once):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\desktop_tracker\install_native_enforcer.ps1
```

No-admin keep-alive (Task Scheduler, native only):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\desktop_tracker\install_enforcer_service.ps1 -Start
```

## Smoke (must pass)

```bat
scripts\desktop_tracker\run_native_enforcer_console.bat
```

1. Open http://127.0.0.1:5173/productivity/focus (login if needed).
2. Enforcer card: set kill list to `notepad.exe` → **Arm hard block**.
3. Open Notepad → process dies within ~2s.
4. Focus shows **Last kill** and status source `enforcer_status.json`.
5. Optional zero-Python proof:
   ```bat
   taskkill /F /IM python.exe /T
   ```
   Open Notepad again → still dies (console enforcer still running).
6. Restart `run.bat` for SoftLand/API. Open Edge, browse a site a minute.
7. Open `/productivity` desktop stats → **Microsoft Edge** with nested site (not bare process time from native).

## Files

| File | Role |
|------|------|
| `data/behavior/enforcer_policy.json` | Focus writes; native reads |
| `data/behavior/enforcer_status.json` | Native writes ~2.5s |
| `data/behavior/enforcer_owner.lock` | Ownership heartbeat |
| `data/behavior/enforcer_policy.json.example` | Copy template |

## If something fails

| Symptom | Fix |
|---------|-----|
| Missing exe | `build_native_enforcer.bat` |
| Arm does nothing | API up? Check policy file exists after Arm |
| Status stale | Enforcer console/service running? |
| Edge missing from stats | Reload SelfTracker; browse with focus on tab |
| Double browser time | Native skips browsers; desktop ignore list skips browsers without `source=extension` |
