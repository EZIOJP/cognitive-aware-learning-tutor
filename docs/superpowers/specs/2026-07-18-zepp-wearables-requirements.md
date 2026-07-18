# Requirements — Zepp / Amazfit → CALT Wearables Bridge

**Date:** 2026-07-18  
**Status:** Approved direction (user: no Google Calendar; Mini Program → custom endpoint; phone notifications for plans)  
**Related:** Study gap planner, Life Tracker, Productivity Plan  
**Companion LLD:** [2026-07-18-zepp-wearables-bridge-lld.md](./2026-07-18-zepp-wearables-bridge-lld.md)

---

## 1. Goal

1. **Health dump:** Amazfit (Zepp OS 5) Mini Program reaches **our custom CALT endpoint** and posts processed sleep/health data (no Google, no Home Assistant required).  
2. **Active plans pull:** On every successful (or periodic) sync, Mini Program **fetches active / today’s plans** from CALT and refreshes the watch agenda — update whenever connectivity allows.  
3. **Plan reminders:** User gets **notifications for tasks / planned blocks** — primarily from a **CALT app on the phone**; watch shows the same active plan list after sync.

Core loop (bidirectional):

```text
Watch Mini Program
   --BLE--> Phone Zepp Side Service --Wi‑Fi--> CALT
        1) POST  /api/wearables/zepp          → dump sleep/health
        2) GET   /api/wearables/zepp/plans    → active plans (today + soon)
        3) watch UI / local agenda cache      ← update whenever sync succeeds
```

Whenever possible = on manual Sync, on interval timer, after wake, and whenever Side Service is alive and CALT is reachable — last successful plan snapshot stays cached on watch offline.

---

## 2. Explicit non-goals

| Out | Why |
|-----|-----|
| **Google Calendar sync** | User does not want it |
| Amazfit native Calendar CRUD | No public Mini Program API |
| Home Assistant as required middleman | Extra stack |
| Separate Amazfit BLE native app | Undocumented; Mini Program is the supported path |

**Busy time for gap-fill** = CALT planner + routines only (not Google).

---

## 3. How “watch Wi‑Fi → our endpoint” actually works

Zepp Mini Programs do **HTTP from the phone Side Service**, not reliably from the watch alone:

```text
Watch (sensors + Sync UI)
   --BLE-->  Phone Zepp Side Service  --Wi‑Fi/LAN-->  CALT http://<PC-or-server>:8000/api/wearables/zepp
```

So: **Wi‑Fi reaches our custom endpoint** = phone on same network (or Tailscale later) talking to CALT. Watch stays paired to phone. That matches “dumps data to our endpoint” without Google.

Optional later: cloud sidecar if phone Side Service is offline overnight — same endpoint, still no Google.

---

## 4. Mini Program vs phone CALT app (roles)

| Piece | Role |
|-------|------|
| **Zepp Mini Program** | Dump sleep/HR → POST; **pull active plans → GET**; refresh watch agenda whenever sync works |
| **CALT on phone** (Android APK / PWA / future Expo) | **Notifications** for upcoming study/tasks from planner; browse Plan/Today |
| **CALT on PC** | Planner source of truth, ingest, Life Tracker, plans API |

Do **not** use Google to carry reminders to the watch. Prefer:

1. Phone CALT local notifications (primary)  
2. Watch Mini Program pulls `GET /api/wearables/zepp/today-plan` and shows / buzzes if OS allows (secondary)

---

## 5. Functional requirements

### FR-1 Health ingest (must)
- `POST /api/wearables/zepp` — versioned JSON, shared token, upsert by local date.
- Processed sleep (score, total/deep min, start/end) → Life Tracker.
- Prefer wearable over same-day manual sleep by default.

### FR-2 Automatic dump + plan refresh (must)
- Mini Program: interval + manual Sync; Side Service `fetch` to CALT base URL from Settings.
- **Each sync cycle (whenever possible):**
  1. `POST` health dump (if new sensor data).
  2. `GET` active plans (today + next N hours / rest of day).
  3. Replace watch-side plan cache; update UI.
- If POST fails but GET works (or vice versa), still apply the successful half; surface partial error.
- Settings: `base_url`, `ingest_token`, `interval_min` (default 15–30), `plan_horizon_hours` (default 24).
- `last_sync_at`, `last_plans_at`, last error visible on watch Settings and CALT UI.

### FR-3 Plan / task notifications (must)
- CALT phone client schedules local notifications from **planner blocks** (title, start time, lead minutes e.g. 5/10).
- Source of truth remains CALT SQLite planner — **not** Google Calendar.
- User can enable/disable notification channel in CALT phone settings.
- Watch list must stay aligned with the same planner rows returned by plans GET (same IDs/titles/times).

### FR-4 Watch active plans (must — not optional)
- `GET /api/wearables/zepp/plans?from=&to=` (or `/today-plan`) returns active/scheduled blocks for the user.
- Include at least: `id`, `title`, `category`, `start_at`, `end_at`, `status`, `source`.
- Filter: not cancelled; prefer `scheduled` / `in_progress` / due today.
- Device App shows agenda from cache; refresh on every successful plans GET.
- Offline: show last cached plans with “stale” hint if older than interval × 2.

### FR-5 Planner sleep soft (should)
- Low sleep → softer next smart daily load; badge explains why.
- Opt-in or default-on TBD (default **on** unless user turns off).

### FR-6 Processed data (must)
- Ingest firmware/cloud **summaries**, not raw PPG streams.

---

## 6. Non-functional

- Local-first; LAN endpoint (`http://192.168.x.x:8000`); document Tailscale for away-from-home.
- Ingest key required; no open webhook.
- Battery: no continuous HR by default.
- Schema-tolerant JSON (`schema: 1`).

---

## 7. Success criteria

- [x] Sync on watch → sleep appears in CALT Life Tracker without Google or HA.  
- [x] Same sync → watch agenda shows **current active plans** from CALT.  
- [x] Edit/apply plan on PC → next watch sync (or ≤ interval) updates watch list.  
- [x] Re-sync same day upserts sleep, no duplicates.  
- [x] CALT desktop/web fires a notification before a planned study block (P4; phone APK later).  
- [x] No Google Calendar OAuth or sync code in this feature.

---

## 8. Phased delivery

| Phase | Deliverable | Status |
|-------|-------------|--------|
| P1 | FastAPI ingest + plans GET + Life Tracker upsert + last-sync UI | Done |
| P2 | Zepp Mini Program: POST health + GET plans + agenda UI + interval sync | Done (v1.5 full sensors) |
| P3 | Stale cache / partial sync UX on watch | Done |
| P4 | CALT local notifications from planner blocks | Done (web/desktop; phone APK later) |
| P5 | Sleep → planner load soft; optional cloud sidecar | Done (sleep soft; sidecar deferred) |

---

## 9. Defaults (locked from user direction)

| Decision | Choice |
|----------|--------|
| Google Calendar | **No** |
| Dump path | Mini Program → **custom CALT endpoint** |
| Plans path | Same sync cycle → **GET active plans** → update watch whenever possible |
| Notifications | **CALT phone app** primary; watch agenda always refreshed on sync |
| Cloud sidecar | Optional later, same ingest |
