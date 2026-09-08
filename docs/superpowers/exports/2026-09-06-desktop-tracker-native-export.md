# CALT Desktop Tracker — Native Enforcer Export

**Date:** 2026-09-06  
**Binary:** `native/calt_enforcer` → `calt_enforcer.exe`  
**Legal:** CALT original C++. No Cold Turkey code.

---

## 1. Responsibility

| Does | Does not |
|------|----------|
| Read `enforcer_runtime` from SQLite | SoftLand / browser redirects |
| Kill listed processes when armed+locked | Own Focus UI |
| Write non-browser `tracked_sessions` | Count Edge tab URLs (SelfTracker does) |
| Hold `enforcer_owner.lock` | Replace Python gate policy |

---

## 2. Source map

| File | Role |
|------|------|
| `native/calt_enforcer/README.md` | Build notes |
| `src/main.cpp` | Console / `--service` entry |
| `src/kill.cpp` | Process kill loop |
| `src/policy_db.cpp` | Read `enforcer_runtime` |
| `src/session_db.cpp` | Foreground → SQLite (**skips browser exes**) |
| `src/owner_lock.cpp` | Ownership lock file |
| `src/win_service.cpp` | Windows Service loop |
| `src/foreground.cpp` | Current FG window exe/title |

Python publish (kill list): `backend/behavior/enforcer_runtime_publish.py`  
Status probe: `backend/behavior/native_enforcer_status.py`  
Category backfill: `backend/behavior/native_session_backfill.py`

---

## 3. Build / install scripts

| Script | Purpose |
|--------|---------|
| `scripts/desktop_tracker/build_native_enforcer.bat` | CMake build + copy to Inno `installer_payload/bin/` |
| `scripts/desktop_tracker/run_native_enforcer_console.bat` | Foreground debug (sets `CALT_DB`) |
| `scripts/desktop_tracker/install_enforcer_service.ps1` | **No admin** — Task Scheduler at logon (native preferred) |
| `scripts/desktop_tracker/install_native_enforcer.ps1` | **Admin** — Windows Service `CALTEnforcer` |
| `scripts/desktop_tracker/uninstall_native_enforcer.bat` | Remove service / helpers |
| `scripts/desktop_tracker/compile_installer.bat` | Inno Setup compile |
| `scripts/desktop_tracker/install_calt_desktop.iss` | Setup project `0.2.1-v2d-native` |

Env:

- `CALT_DB` → `data\vocab_app.db`
- `CALT_ENFORCER_LOCK` → `data\behavior\enforcer_owner.lock`

---

## 4. Session rules (C++)

Mirrored from Python tracker maturity:

- Idle flush ~300s  
- Sleep/wall gap  
- Max chunk ~600s  
- **Browsers skipped** (Edge/Chrome/…) so SelfTracker owns tab time  

Rows: `source=desktop_tracker`, `category_source=native` → Python backfills `category` on Focus/stats refresh.

---

## 5. Verify

```bat
scripts\desktop_tracker\build_native_enforcer.bat
scripts\desktop_tracker\run_native_enforcer_console.bat
```

Or Task Scheduler:

```bat
powershell -ExecutionPolicy Bypass -File scripts\desktop_tracker\install_enforcer_service.ps1 -Start
```

Check Focus enforcer card: owns / last kill.  
Check SQLite: new rows with `category_source=native` after switching non-browser apps.
