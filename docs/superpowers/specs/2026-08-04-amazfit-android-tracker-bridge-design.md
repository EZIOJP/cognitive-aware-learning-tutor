# Amazfit + CALT Android tracker bridge (2026-08-04)

Local-first honesty: what ships on phone vs watch vs API.

## Goal

Wire **T-Rex 3 / Zepp** and the **CALT Android** surface to desktop tracker day rules
(bible → plan → browser mode · hard-block · tracker alive) without faking a full
CALT OS on the watch.

## What ships

| Layer | Deliverable |
|-------|-------------|
| **API** | `GET /api/behavior/day-status` (JWT) — morning + `browser_mode` + hard-block + `tracker_alive` + wearables last sync + notify hint |
| **API** | `GET /api/behavior/mobile-alerts` — drain local-notification queue for Android |
| **Hub** | `GET /api/hub/day-status` (wearable key) on tracker `:8765` for watch/phone when FastAPI is down |
| **Android (in-repo)** | `packages/calt-android-tracker` Expo **Tracker** screen — checklist, arm/disarm (JWT), confirm plan, soft wake, wearables glance, local notify relay |
| **Android (external)** | Timetable APK `com.calt.timetable` still built from `New folder (6)/calt-timetable` → `scripts/publish_calt_apk.bat` |
| **Zepp** | `packages/calt-zepp` **3.2.0** — fetches day-status, shows mode badge, notifies on Bible/plan/mode fingerprint change |

## How Amazfit gets alerts

```text
Mode / morning change
    → build_day_status enqueues pending_mobile_alerts.json
    → CALT Android polls /api/behavior/mobile-alerts → expo-notifications (local)
    → Zepp phone app "notification mirror" (user setting) → watch glance

AND / OR

Watch Sync (Today)
    → GET /api/hub/day-status
    → cache fingerprint → calt_pending_mode_notify
    → App Service flushModeNotify → @zos/notification
```

There is **no** CALT-written hardware smart alarm. Soft wake remains
`morning.suggested_wake` only.

## Limits (do not fake)

| Not available | Reality |
|---------------|---------|
| Full CALT UI on watch face | Would need a dedicated Zepp OS app/watchface project; mini-program is the supported path |
| Arbitrary watch APK install of React Native | Amazfit does not run Expo APKs |
| Writing T-Rex smart alarms from CALT | Deferred — device-side only |
| Arm hard-block with wearable ingest key | Policy writes require JWT (`PUT /api/behavior/policy`) |
| Invent sitting minutes from stand hours | Only when watch payload includes sitting/sedentary fields |

## Auth

- **day-status (FastAPI):** same solo/JWT as distraction-gate  
- **day-status (hub):** `X-CALT-Wearable-Key` / Bearer = `calt-local-wearables`  
- **Arm / disarm / confirm plan:** JWT only  

## Reload

1. Restart API (`run.bat`) so `/api/behavior/day-status` is mounted.  
2. Restart desktop tracker so hub exposes `/api/hub/day-status`.  
3. Sideload Zepp: `packages\calt-zepp\sideload.bat` (3.2.0).  
4. Expo Tracker: `cd packages\calt-android-tracker && npm i && npx expo start`.
