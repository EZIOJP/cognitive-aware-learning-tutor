# Zepp OS 5 — Implementation logic & steps (from official docs)

**Date:** 2026-07-18  
**Tied to:** [requirements](./2026-07-18-zepp-wearables-requirements.md) · [LLD](./2026-07-18-zepp-wearables-bridge-lld.md)

This note rechecks [docs.zepp.com](https://docs.zepp.com) for what we actually need. **Verdict: Mini Program (+ optional Widget/Shortcut), not a custom watchface.**

---

## 1. Watchface vs Mini Program — which do we need?

| Surface | Can POST to CALT? | Can show **our** plans? | Role for CALT |
|---------|-------------------|-------------------------|---------------|
| **Watchface** | **No** (no Side Service `fetch`; only system `hmUI.data_type.*` like steps/HR/system sleep) | **No** custom text from our API | Skip for v1 |
| **Mini Program (Device App)** | Via Side Service | Yes — full agenda UI + Sync | **Required** |
| **SecondaryWidget** (swipe left from watchface) | Not directly; cache from Mini Program pages | Yes — next 1–2 blocks (glance) | **Recommended** later |
| **AppWidget / Shortcut Card** (negative screen) | Same as widget | Yes — compact “next plan” | **Recommended** later |
| **App Service** (background, OS 3+) | Indirect (trigger sync / notify) | Via `@zos/notification` | **Should** for wake/sleep events |

**Why not a custom watchface?**  
Watchfaces bind to **system** data types ([watchface data_type](https://docs.zepp.com/docs/watchface/api/hmUI/widget/data_type/), [editable watchface](https://docs.zepp.com/docs/watchface/api/hmUI/widget/edit_watchface/)). They do **not** run Side Service HTTP to your endpoint and cannot list CALT planner rows. Building a watchface would not implement “dump health + pull active plans.”

**Closest “always visible” UX without a watchface:**  
Add a **SecondaryWidget** (“CALT · next block”) that reads **localStorage** filled by the last sync — then tap → open full Mini Program. Docs: [SecondaryWidget](https://docs.zepp.com/docs/guides/framework/device/secondary-widget/). Caution from docs: widgets **cannot** do live BLE themselves — sync in **Page** / Side Service, then persist for the widget.

---

## 2. Doc-backed architecture (required pieces)

From [Overall Architecture](https://docs.zepp.com/docs/guides/architecture/arc/):

```text
Device App (@zos/sensor Sleep/HR, UI, localStorage plans cache)
    ↔ BLE MessageBuilder (ZML / shared/message.js)
Side Service (fetch POST + GET to CALT)     ← only place with HTTP
Settings App (base_url, token, interval)
[+ optional SecondaryWidget / AppWidget reading cache]
[+ optional App Service + system events + @zos/notification]
```

Official samples to clone logic from:

| Sample | Use |
|--------|-----|
| [post-health-data](https://github.com/zepp-health/zeppos-samples/tree/main/application/2.0/post-health-data) | Health → server pattern |
| [fetch-api](https://github.com/zepp-health/zeppos-samples/tree/main/application/2.0/fetch-api) | Side Service `fetch` + MessageBuilder |
| [Calories + widget](https://docs.zepp.com/docs/guides/framework/device/secondary-widget/) | SecondaryWidget / Shortcut Card |
| [3.0-feature / App Service](https://docs.zepp.com/docs/guides/framework/device/app-service/) | Background + notifications |

---

## 3. APIs / logic we must use

### 3.1 Permissions (`app.json`)

```text
data:user.hd.sleep
data:user.hd.heart_rate          # if HR included
event:os.health.sleep_status     # optional App Service (API_LEVEL 3+)
event:os.system.sleep_mode       # wake → sync
```

### 3.2 Sleep (processed) — Device App

[`@zos/sensor` Sleep](https://docs.zepp.com/docs/reference/device-app-api/newAPI/sensor/Sleep/):

1. `sleep.updateInfo()` — system only refreshes ~every 30m otherwise  
2. `getInfo()` → `score`, `deepTime`, `startTime`, `endTime`, `totalTime`  
3. `getStage()` / `getNap()` when available  
4. Pack into health snapshot for Side Service  

### 3.3 Heart (optional, light)

[`HeartRate`](https://docs.zepp.com/docs/reference/device-app-api/newAPI/sensor/HeartRate/): `getLast()`, `getResting()` — **do not** leave `onCurrentChange` on for auto sync (battery).

### 3.4 BLE bridge

[MessageBuilder](https://docs.zepp.com/docs/guides/best-practice/bluetooth-communication/):

- Device: `messageBuilder.connect()` in `app.js` `onCreate`; `disConnect` in `onDestroy`  
- Device → Side: `request({ method: 'SYNC_ALL', params: { health } })`  
- Side → Device: `response({ healthOk, plans, errors })`  
- Polyfill: `shared/device-polyfill`  

### 3.5 HTTP — Side Service only

[Fetch API](https://docs.zepp.com/docs/reference/side-service-api/fetch/):

```js
// POST health
await fetch({
  url: `${base}/api/wearables/zepp`,
  method: 'POST',
  headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
  body: JSON.stringify(healthBody),
})
// GET plans
const res = await fetch({
  url: `${base}/api/wearables/zepp/plans?horizon_hours=24`,
  method: 'GET',
  headers: { Authorization: `Bearer ${token}` },
})
const data = typeof res.body === 'string' ? JSON.parse(res.body) : res.body
```

Parse `res.body` as string **or** object (docs compatibility note).

### 3.6 Settings

Settings Storage: `base_url`, `ingest_token`, `interval_min`, `plan_horizon_hours`.  
Side Service `addListener` on changes → restart timer.

### 3.7 Persist plans on watch

`@zos/storage` `localStorage` (or fs): last `plans[]` + `plansFetchedAt` so Widget/offline UI work.  
Docs: widgets should **not** open MessageBuilder — read storage only; full sync in main Page.

### 3.8 “Whenever possible” triggers

| Trigger | Doc mechanism |
|---------|----------------|
| Manual Sync button | Page → `request SYNC_ALL` |
| Interval while Side Service up | Side Service timer → `call` device for health or use last snapshot + GET plans |
| After sleep / wake | [System Events](https://docs.zepp.com/docs/guides/framework/device/system-event/) → App Service → nudge sync / notification |
| Watch reminder for a block | [`@zos/notification`](https://docs.zepp.com/docs/guides/version-info/new-features-30/) and/or [`@zos/alarm`](https://docs.zepp.com/docs/guides/framework/device/app-service/) after plans GET (OS 3+) |

Phone CALT notifications remain primary for reliability; watch notification is additive when App Service is allowed.

---

## 4. Sync cycle (implementation logic)

```text
SYNC_ALL (manual | timer | sleep_exit event):
  Device: build health from Sleep (+ optional HR)
  Device → Side: request SYNC_ALL { health }
  Side:
    POST /api/wearables/zepp          # dump (ignore if empty)
    GET  /api/wearables/zepp/plans    # always try
    return { healthOk, plans, errors }
  Device:
    localStorage.set('calt_plans', plans)
    redraw agenda (+ notify Widget via storage)
  Optional App Service:
    schedule @zos/notification / alarm for next plan start − lead
```

Partial OK: plans refresh even if POST fails.

---

## 5. Ordered build steps

### A. Tooling (once)
1. Zepp developer account + [Zeus CLI](https://docs.zepp.com)  
2. Confirm device in [device list](https://docs.zepp.com/docs/reference/related-resources/device-list/) — OS 5, API_LEVEL ≥ 3 preferred (App Service / notifications)  
3. Simulator + sideload path via Zepp app  

### B. CALT backend (P1) — before watch polish
4. `POST /api/wearables/zepp` + token  
5. `GET /api/wearables/zepp/plans`  
6. Life Tracker upsert + unit tests  
7. Verify with `curl` from phone browser to LAN IP `/health` and plans  

### C. Mini Program skeleton (P2)
8. `zeus create calt-zepp` (OS 2+/3+ Empty)  
9. Copy `shared/message.js` + polyfill from fetch-api / post-health-data samples  
10. Wire `app.js` MessageBuilder connect  
11. Settings App: URL + token + interval  
12. Side Service: SYNC_ALL → POST + GET  
13. Page: Sync button, agenda list from response + localStorage  
14. Permissions for sleep (+ events if App Service)  

### D. Glance UX (optional, not watchface)
15. `secondary-widget/index.js` — show next plan title/time from localStorage  
16. Click → `router.push` main Page  
17. Optional AppWidget on negative screen  

### E. Background / alerts (P3–P4)
18. App Service on `sleep_mode` exit / `sleep_status` → trigger sync  
19. After plans GET, set watch notifications for next block (if API_LEVEL allows)  
20. CALT phone app local notifications (primary alerts)  

### F. Hardening
21. Stale plans banner  
22. Token/URL validation + error toast  
23. Battery: interval ≥ 15 min; no continuous HR  

---

## 6. What we will **not** build (docs say so)

- Custom **watchface** for CALT plans/sync  
- Direct Device App `fetch` (not the documented path)  
- Writing Amazfit system Calendar  
- Google Calendar  

---

## 7. Recommendation (locked)

```text
Must:     Mini Program (Device + Side Service + Settings) + CALT APIs
Should:   SecondaryWidget / Shortcut for “next plan” glance
Can:      App Service + system notification for wake sync / wrist buzz
Skip:     Custom watchface
```

That is the doc-correct way to get: **dump sleep/health + get active plans + update whenever sync is possible**, with a glance that *feels* watchface-adjacent without fighting the watchface API.
