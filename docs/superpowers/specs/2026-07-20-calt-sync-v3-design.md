# CALT Sync v3 — tracker hub + watch UX rebuild

**Date:** 2026-07-20  
**Status:** Partially superseded (2026-08-15) — watch UX is now **manual health dump only** (see [CALT_SYNC_MANUAL_DUMP.md](../../CALT_SYNC_MANUAL_DUMP.md) / package **4.0.0**). Tracker hub `:8765` remains the Base URL.  
**Package:** `packages/calt-zepp` (appId `1088801`)  
**Companion:** desktop tracker LAN hub (`backend/behavior/`)  
**Supersedes (partially):** quiet-background + UI parts of `2026-07-18-calt-sync-v2-design.md`

## Problem

1. CALT Sync depends on FastAPI `:8000` (`run.bat`), which is often not running — sync fails from the phone Side Service.  
2. The desktop tracker **is** usually running, but it has no LAN HTTP surface for the watch.  
3. Watch UI is cramped (half-width buttons, fixed layout, hard to use on 480×480).  
4. Background App Service fires **hourly + sleep/wear notifications with vibrate** → constant spam.  
5. User wants a delayed **Shut down PC** from the watch (30s countdown + cancel).

## Goals (v3 — locked scope)

| # | Goal |
|---|------|
| G1 | Desktop tracker exposes a **LAN hub** (default port **8765**) that CALT Sync uses as Base URL |
| G2 | Wearables ingest + calendar/plans work via hub **without** requiring `run.bat` when SQLite/services can run in-process |
| G3 | **Shut down PC**: watch → hub → **~30s delay** + on-PC toast/tray + **cancel** endpoint |
| G4 | **Quiet background**: no hourly notifications; morning notify at most once/day (default **Morning only**, phone setting Off / Morning / On) |
| G5 | **Scrollable Today UI**: large full-width buttons, heavy spacing, crown/swipe scroll |
| G6 | **Focus lock glance** from distraction gate (`locked` / minutes left / unlocked) |
| G7 | **Goal ring** — productive minutes vs daily goal (simple text/ring on Today) |
| G8 | **Lock screen** remote (same hub as shutdown; no delay required, or short 3s) |
| G9 | Soft-day chip kept/improved when hub returns `soft_day` |

## Non-goals (v3)

- Distraction-guard Windows Service / AppLocker (separate follow-up)  
- “I’m distracted” ping, Find my PC, quick journal, Pomodoro-on-Sync (→ **v3.1**)  
- Merging Adaptive Focus into CALT Sync (stay separate `1088802`)  
- Writing Amazfit **system** calendar events (still impossible)  
- Browser site blocking (Cold Turkey)

## Architecture

```text
Watch (CALT Sync UI)
    │  BLE message
    ▼
Phone Side Service (Zepp app-side)
    │  HTTP + Bearer token
    ▼
Desktop tracker LAN hub :8765
    ├── /health
    ├── /api/wearables/zepp/*   (ingest, calendar, plans, actions)
    ├── /api/hub/gate           (distraction gate + goal progress)
    ├── /api/hub/shutdown
    ├── /api/hub/shutdown/cancel
    └── /api/hub/lock
         │
         ├─► SQLite + existing wearables/planner services (in-process)
         └─► optional forward to localhost:8000 when FastAPI is up
```

**Auth:** same Bearer token as today (`calt-local-wearables` / settings `wearables_ingest_key`).

**Bind:** `0.0.0.0:8765` (LAN). Document Windows Firewall allow for Python. Never recommend `localhost` in phone settings.

## Hub API (tracker)

| Method | Path | Behavior |
|--------|------|----------|
| GET | `/health` | `{ ok, service: "calt.tracker_hub", version }` |
| POST | `/api/wearables/zepp/ingest` | Same contract as FastAPI wearables ingest |
| GET | `/api/wearables/zepp/calendar` | Same as FastAPI |
| GET | `/api/wearables/zepp/plans` | Same + `soft_day` |
| POST | `/api/wearables/zepp/plans/{id}/start\|complete\|snooze` | Same |
| GET | `/api/hub/gate` | `{ locked, unlocked, productive_minutes, daily_goal_minutes, remaining_minutes, hard_block_enabled }` |
| POST | `/api/hub/shutdown` | Start 30s countdown; return `{ ok, seconds, cancel_path }` |
| POST | `/api/hub/shutdown/cancel` | Abort pending shutdown |
| POST | `/api/hub/lock` | `rundll32 user32.dll,LockWorkStation` (Windows) |

**Shutdown UX on PC:** tray balloon / MessageBox-lite toast: “Shutting down in 30s — cancel from watch or POST cancel”. Use `shutdown /s /t 30` when countdown starts, or internal timer then `shutdown /s /t 0`; prefer **Windows `shutdown /s /t 30`** so OS cancel (`shutdown /a`) also works; hub cancel calls `shutdown /a`.

**Implementation sketch:** `backend/behavior/tracker_hub.py` — `ThreadingHTTPServer` (or waitress) started from `desktop_tracker` / `tracker_service` on a daemon thread. Reuse `backend/wearables/*` and distraction-gate helpers with a DB session factory (same pattern as tracker storage).

## CALT Sync watch app (v3.0.0)

### Background service (`app-service/sync.js`)

- Hourly: write `calt_hourly_snap` **only** — **no** `notificationMgr.notify`  
- Morning / sleep_status: set `calt_pending_sync`; notify **only if** settings allow and **not already notified today** (localStorage day key)  
- Phone setting `notify_mode`: `off` | `morning` | `on` (default `morning`)

### Today page (scrollable)

Root: `SCROLL_LIST` or equivalent vertical scroll container (Zepp OS 3).

**Scroll order (large taps):**

1. Title + last sync status  
2. **Gate line** — e.g. `Locked · 1h 12m` / `Unlocked` / `Gate off`  
3. **Goal line** — e.g. `Focus 95 / 240 min` (optional simple progress bar widget if easy)  
4. Soft-day chip  
5. Health strip (steps · sleep · HR · stress)  
6. Next calendar block (large wrap text)  
7. **Sync now** — full width, ~0.18–0.22× height  
8. **Calendar** — full width  
9. **Plans** — full width  
10. **Shut down PC** — danger color; status becomes `Shutdown in 30s…`  
11. **More** → nested page: Lock PC, Focus, Sys Cal, Test, Log  

Spacing: pad ≥ 6% width; gap between buttons ≥ 12–16px; avoid 2-column home rows.

### Phone settings

- Base URL default hint: `http://<LAN-IP>:8765`  
- Ingest token (unchanged)  
- Notify mode  
- Optional: shutdown delay seconds (default 30) if easy; else fixed 30 on hub

### Version

- `app.json` → `3.0.0` / code bump  
- README: tracker hub required; `run.bat` optional

## Success criteria

1. With tracker running and FastAPI **stopped**, phone Test + Sync against `:8765` succeeds for health ingest (and plans if DB present).  
2. Hourly background tick produces **zero** notifications.  
3. Morning notify ≤ 1 per local day when mode is `morning`.  
4. Today page scrolls; primary actions are full-width and usable with a finger on T-Rex 3.  
5. Shut down from watch starts OS 30s shutdown; cancel from watch aborts (`shutdown /a`).  
6. Gate + goal lines update after Sync when policy exists.  
7. Lock PC locks the Windows session.

## Deferred (v3.1+)

- I’m distracted ping  
- Find my PC (sound)  
- Quick journal buttons  
- Pomodoro controls on Sync  
- Mute / media pause remotes  
- Dual-process distraction enforcer service  

## Risks

| Risk | Mitigation |
|------|------------|
| Firewall blocks :8765 | Install/startup bat opens rule; phone browser `/health` check |
| Hub DB vs FastAPI dual writers | Same SQLite file; short transactions; prefer in-process services |
| Accidental shutdown | 30s + cancel + danger styling + More vs primary Sync |
| Zepp SCROLL API quirks | Prototype on device early; fallback: multi-page if scroll fails |

## Open decisions (defaults locked)

| Topic | Decision |
|-------|----------|
| Port | 8765 |
| Shutdown delay | 30s via `shutdown /s /t 30` |
| Notify default | `morning` |
| Remote extras in v3 | Lock only (+ shutdown) |
| Cool extras | Author pick: gate glance + goal ring + soft-day |

## Review checklist

- [ ] User OK with locked v3 scope  
- [ ] User OK deferring Find-my-PC / distracted ping  
- [ ] Proceed to implementation plan → code  
