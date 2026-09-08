# Owner task list + agent QoL (2026-09-07)

## Your tasks (only you can do these)

- [ ] **Admin stay-alive** — run once as Admin:
  ```powershell
  powershell -ExecutionPolicy Bypass -File scripts\desktop_tracker\install_native_enforcer.ps1
  ```
- [ ] **Reload extensions** — `edge://extensions` → SelfTracker + CALT Gate → Reload
- [ ] **Morning smoke** — see [2026-09-07-morning-smoke.md](./2026-09-07-morning-smoke.md)
  1. Console or service enforcer running
  2. Focus → Arm `notepad.exe` → Notepad dies
  3. Edge browse → `/productivity` shows Microsoft Edge + site

## Agent done (QoL this pass)

| Item | Status |
|------|--------|
| Focus health strip (stale status + start CTA) | ☑ |
| Poll every 2.5s + Arm/Disarm success hint | ☑ |
| SoftLand vs OS kill copy on Now card | ☑ |
| Voice hard_block also writes `enforcer_policy.json` | ☑ |
| `status_age_s` on Focus enforcer snapshot | ☑ |
| Gate publish no longer overwrites Focus OS arm | ☑ |
| SoftLand label (not dual “Armed”) on Productivity | ☑ |
| Focus Edge reload strip + native setup on Productivity | ☑ |

## Still parked (not daily QoL)

- F2 native session category backfill
- Web kill toast
- Tier 2 folder/title blocks
