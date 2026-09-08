# CALT maturity checklist (Cold Turkey–*ideas* only)

**Created:** 2026-09-07  
**Updated:** 2026-09-07 (Tier 1 implemented)  
**Purpose:** Reminder when you forget — mature *capabilities*, never CT code.

---

## Locked rules (never break)

- **No** Cold Turkey binaries, decompile, exact internals, extension IDs, registry keys, SQLite schema, or protocol strings.
- **Yes** public knowledge: native messaging spec, process lists, window titles, policy JSON.
- **Desktop tracker:** `calt_enforcer` runs with **0% Python** (policy/status JSON). Python = SoftLand/study web only.

---

## Already done (don’t redo)

| Item | Where |
|------|--------|
| Zero-Python enforcer (policy JSON + status JSON) | `native/calt_enforcer`, `enforcer_policy.json`, `enforcer_status.json` |
| Focus Arm/Disarm → policy file | `/productivity/focus` |
| Non-browser session track; browsers skipped | `session_db.cpp` |
| Edge = Microsoft Edge + active tab | SelfTracker + `browser_labels.py` |
| Broad browser names (Tier 1 #1) | `IsBrowserExe`, `browser_labels.py`, SelfTracker UA map |
| Anti-tamper while locked (Tier 1 #2) | Taskmgr + process explorers + w32tm in kill merge |
| Native Messaging Host ping (Tier 1 #3) | `native/calt_msg_host/` |
| Strong lock modes (Tier 1 #4) | policy JSON + Focus UI + API 403 + native sticky |
| Task Scheduler / service install scripts | `scripts/desktop_tracker/` |
| Export pack | `docs/superpowers/exports/` |

---

## Tier 1 status

| # | Item | Status |
|---|------|--------|
| 1 | Broad browser names | ☑ |
| 2 | Anti-tamper basics | ☑ |
| 3 | Native Messaging Host skeleton | ☑ |
| 4 | Strong lock modes | ☑ |
| 5 | Admin service as default | ☑ scripts prefer service — **Owner:** run `install_native_enforcer.ps1` once as Admin |

---

## Tier 2 — High value after Tier 1

| Feature | Notes | Status |
|---------|--------|--------|
| Folder + window-title app blocking | Path prefix + title substring in C++ | ☐ |
| Block entire internet except whitelist | Gate + native host `*.*` + exceptions | ☐ |
| Usage allowances / breaks | Extend Focus earned minutes / policy quotas | ☐ |
| YouTube channel / path rules | SelfTracker URL → Gate pattern match | ☐ |
| Hard-to-lie status | `enforcer_status.json` — React display-only | ☑ mostly done |

---

## Tier 3 — Nice later

- Motivational block page / “Pause for a Cause”
- Pre-made category blocklists (ship JSON lists)
- Tamper-resistant statistics
- Whole-machine lock (logoff/shutdown) — powerful; use carefully

---

## Owner smoke

```bat
scripts\desktop_tracker\build_native_enforcer.bat
scripts\desktop_tracker\build_calt_msg_host.bat
powershell -ExecutionPolicy Bypass -File scripts\desktop_tracker\install_native_enforcer.ps1
scripts\desktop_tracker\run_calt_desktop.bat
REM Focus → Arm with lock mode → open Notepad / Task Manager → should die
```

- Policy: `data/behavior/enforcer_policy.json`
- Status: `data/behavior/enforcer_status.json`

---

## Bottom line

Want CT’s *feel* (browsers, hard locks, stay-alive, anti-tamper, extension↔native).  
Never CT’s *code*.  

**Next coding session:** Tier 2 (folder/title blocks, allowances, YouTube rules).
