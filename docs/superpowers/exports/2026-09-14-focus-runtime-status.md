# Focus runtime status — 2026-09-14 ~00:15 IST

**Verdict:** App is **running and gateway-healthy** after a restart. SoftLand and Arm are both **OFF** with an empty kill list (post block-mode suite restore). Nothing is blocking sites or apps until you turn them on again.

---

## What was broken

| Symptom | Root cause |
|---------|------------|
| Settings / Unlock / Arm writes failing | `\\.\pipe\calt_enforcer_cmd` timed out |
| Stale `enforcer_status.json` (`pid` 6060, `focus_running: true`) | Enforcer + Focus were **not running**; status left over from ~2026-09-13 17:39 IST |
| Stale `enforcer_owner.lock` | Dead PID 6060 still claimed ownership |

No Windows service `CALTEnforcer` is installed — console enforcer dies when that process exits / PC reboots.

---

## What we did

1. Removed stale lock (holder PID dead).
2. Started `calt-focus\backend\calt_enforcer\build\calt_enforcer.exe` (pid **38808**).
3. Started `calt-focus\backend\calt_focus\build\calt_focus.exe` (pid **26508**).
4. Verified gateway + SoftLand decide + day loop.

---

## Live verification (fresh)

| Check | Result |
|-------|--------|
| `status.snapshot` | **ok** |
| `day.status` | **ok** — ledger 6000s; reward_available **0**; passes_used 0/2 |
| `reward.status` | **ok** |
| `day.loop_snapshot` | **ok** — date 2026-09-14; bible_done true; plan_confirmed true; dual_gate_ok false (no plan minutes yet) |
| SoftLand `get_mode` (youtube / porn / meet / github) | all **allow** / `softland_off` |
| JSON ↔ SQLite Arm | both **disarmed**, `exes: []` |
| SoftLand enabled | **false** (JSON + SQLite) |
| Focus tray process | **running** (`focus_running: true`) |
| Named pipe | `calt_enforcer_cmd` present |

---

## Current policy (owner-facing)

| Switch | State | Meaning |
|--------|-------|---------|
| SoftLand | **OFF** | Browser Gate will not block any site |
| Arm | **OFF** | No process kills |
| Kill list | **empty** | Suite restore wiped game EXEs — re-add Steam/etc. in Focus → Blocker / Apps if you want kills |
| Unlock password | still set (`test-bypass-pw` from suite) | Change in Settings → Unlock if you do not want the test password |
| Site rules | allow: `meet.google.com`; watch/block extras empty | Built-in watch/porn/social heuristics still apply when SoftLand is ON |
| Schedule | Mon–Fri 09:00–18:00 STUDY | Only matters when SoftLand is ON |

SoftLand ON ≠ Arm. Turn each on intentionally.

---

## How to use it now

1. Open **CALT Focus** from the tray (already started).
2. Prefer **Reload UI** once if Settings looks stale.
3. To block sites: Settings → SoftLand **ON** (disabling later may require typing UNLOCK).
4. To kill games: re-add EXEs under Apps / Blocker, set password lock if desired, then **Arm**.
5. After reboot: start enforcer again, or install stay-alive once as Admin:

```powershell
powershell -File scripts\desktop_tracker\install\install_native_enforcer.ps1
```

Quick restart helpers:

```bat
scripts\desktop_tracker\run\run_native_enforcer_console.bat
calt-focus\restart_calt_focus.bat
```

---

## Known gaps (not fixed this pass)

1. **No installed enforcer service** — console process only; will not survive reboot / crash.
2. **Empty Arm list** — intentional after suite restore; not an engine bug.
3. **SoftLand off** — intentional; live browser blocking not active.
4. **Day loop** — no planned/tracked minutes yet today (`dual_gate_ok: false`).
5. **Reward balance** — `reward_available: 0` (earned 2 + granted 3 − spent 5).
6. Earlier suite report still valid: 73/73 PASS on SoftLand/Arm matrix; sticky disarm + SQLite sync fixes remain in the tree.

---

## Product reminder

- Focus UI = control plane (`calt_focus.exe` + `dist-focus`).
- Enforcer = kill/SoftLand brain (`calt_enforcer.exe`, zero Python).
- Study `:8000` is optional and is **not** required for SoftLand/Arm.
