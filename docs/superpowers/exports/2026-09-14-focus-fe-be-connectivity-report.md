# Focus FE ↔ BE connectivity + planned features report

**When:** 2026-09-14 ~00:42 IST  
**Verdict:** Connected and repaired. Empty UI was **not** “FE needs Study `:8000`” — it was dead enforcer + empty/mismatched SoT + a Home plan date-range bug.

---

## Root causes (found)

| # | Issue | Effect |
|---|--------|--------|
| 1 | `calt_enforcer` **not running** (stale status / dead lock) | WebView bridge → named pipe timed out; Settings writes locked; day/plan/reward live data failed |
| 2 | SoftLand **site lists desynced** | UI reads `softland_policy.json` (watch/block empty); richer lists sat unused in `softland_site_rules.json` |
| 3 | **No plan blocks for 2026-09-14** | Routines existed; last materialised day was 2026-09-11 → Home/Plan looked empty |
| 4 | **Bug:** `HomeModeBoard` called `fetchPlannerBlocks(day, day)` | Same instant range only returns blocks overlapping that point → Home day timeline empty even when calendar had data |
| 5 | Latest `dist-focus` not remapped until Focus restart | Tray needs rebuild + restart/Reload UI |

Study `:8000` is **not** required for SoftLand / Arm / Plan / day-loop in Focus.

---

## Fixes applied this session

1. Restarted `calt_enforcer` (cleared stale owner lock).
2. Synced site lists via `softland.patch_site_rules` from sidecar → policy:
   - allow: `docs.google.com`, `meet.google.com`
   - watch: `youtube.com`, `reddit.com`, `twitch.tv`
   - block: `python-wrote-this.com`
3. Applied routines for today: `routine.apply` → **9 blocks created** for 2026-09-14.
4. Fixed `HomeModeBoard` to fetch `startOfDay(day)` → `endOfDay(day)`.
5. Rebuilt `dist-focus` (`npm run build:focus`) and restarted `calt_focus.exe`.

**Running now:** `calt_enforcer` + `calt_focus` (latest UI).

---

## Architecture (how FE connects to BE)

```text
calt_focus.exe WebView2
  ├─ https://calt.app        → dist-focus/          (UI)
  ├─ https://calt-data.app   → data/productivity/behavior/  (JSON mirrors)
  └─ chrome.webview.postMessage(enforcer_cmd)
         → named pipe \\.\pipe\calt_enforcer_cmd
         → calt_enforcer.exe (SQLite SoT + SoftLand/Arm/Plan)
```

| Plane | Path | Used for |
|-------|------|----------|
| Read mirrors | `calt-data.app/*.json` | SoftLand policy, day_rollup, enforcer_status |
| Writes / live | `enforcerNativeCmd` → pipe | SoftLand ON/OFF, Arm, plan CRUD, day-loop, reward |
| Not used for SoftLand | Study `:8000` | Vocab/quiz only |

---

## Planned feature execution matrix

| Feature | Backend op / source | Status after fix |
|---------|---------------------|------------------|
| SoftLand policy read | `softland_policy.json` | **OK** — lists populated |
| SoftLand ON/OFF | `softland.set_enabled` | **Ready** (currently OFF by design) |
| Site lists Allow/Watch/Always | `softland.patch_site_rules` | **OK** — synced |
| Arm kill switch | `arm.set` + policy | **Ready** (disarmed; `exes: []` until you re-add games) |
| Day loop snapshot | `day.loop_snapshot` | **OK** |
| Reward / ledger | `reward.status` / `ledger.snapshot` | **OK** (ledger 6000s; reward_available 0) |
| Plan list (today) | `plan.list` | **OK** — **9 blocks** after routine.apply |
| Routines | `routine.list` / `routine.apply` | **OK** — 9 routines; applied today |
| Device block status | `device_block.status` | **OK** (gateway) |
| Glance / productive minutes | `day_rollup.json` | **OK wire**; values still **0** (no tracked sessions yet) |
| Home day timeline | FE fix + plan.list | **Fixed** — rebuild shipped |
| Bible / Journal | Focus life content via gateway | Present; not re-probed in this pass (pipe client) |

---

## What you should see in the tray UI now

1. Open Focus → Home: SoftLand mode **OFF**, site chips with youtube/reddit/twitch, **today’s 9 routine blocks**.
2. Plan / Calendar: blocks for 2026-09-14.
3. Settings: enforcer reachable (no “Enforcer not running” banner). SoftLand still OFF until you turn it on.
4. GlanceBar productive time may still show **0** until the tracker records sessions.

If anything still looks stale: tray **Reload UI** once.

---

## Remaining owner follow-ups

1. **Install enforcer stay-alive** (Admin once) so pipe does not die overnight:
   `powershell -File scripts\desktop_tracker\install\install_native_enforcer.ps1`
2. Re-add **Arm exe list** (Steam/etc.) if you want kills — suite restore left `exes: []`.
3. Turn **SoftLand ON** when you want site blocking (disable requires typing UNLOCK).
4. `day.loop` `planned_minutes` may stay 0 until day-loop recount/confirm path — blocks still show on Home/Plan.
5. Optional: change unlock password away from suite `test-bypass-pw`.

---

## Files touched

- `src/components/productivity/HomeModeBoard.tsx` — plan range fix  
- `data/productivity/behavior/softland_policy.json` — site lists via gateway  
- `dist-focus/` — rebuilt  
- Helpers: `scripts/desktop_tracker/run/_gw_pipe.py`, `_focus_fe_be_probe.py`

---

## Bottom line

**Frontend and backend are connected** through WebView mirrors + enforcer pipe. Empty UI was caused by a **down enforcer**, **empty today’s plan**, **desynced SoftLand lists**, and a **Home fetch bug**. Those are fixed; Focus was rebuilt and restarted with live data for today.
