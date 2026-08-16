# CALT Android Tracker (Expo)

Phone bridge for **desktop tracker / morning rules / day modes**. Not a Zepp watch APK.

The full timetable APK (`com.calt.timetable`) still lives outside this repo
(`New folder (6)/calt-timetable`) and is published via `scripts/publish_calt_apk.bat`.
This package is the **in-repo Tracker screen** that talks to:

| Endpoint | Auth | Purpose |
|----------|------|---------|
| `GET /api/behavior/day-status` | JWT | Aggregate morning + mode + hard-block + tracker + wearables |
| `GET /api/hub/day-status` | Wearable key | Same aggregate via desktop tracker hub `:8765` |
| `GET /api/behavior/mobile-alerts` | JWT | Drain local-notification queue (mirrors to Amazfit if phone→watch notify is on) |
| `PUT /api/behavior/policy` | JWT | Arm / disarm hard-block |
| `POST /api/behavior/morning-plan/confirm` | JWT | Confirm plan CTA |

## Run (dev)

```bat
cd packages\calt-android-tracker
npm install
npx expo start
```

Scan QR with Expo Go on the same Wi‑Fi as the PC. Set **Server** to `http://<PC-LAN-IP>:8000`
(or `:8765` + Prefer hub).

## Build APK (optional)

```bat
cd packages\calt-android-tracker
npx expo prebuild --platform android
cd android
gradlew.bat assembleDebug
```

Or EAS: `npm run build:apk` (needs Expo account).

Copy debug APK wherever you like; the **timetable** download card still uses
`data/downloads/calt-android.apk` from the external project.

## Amazfit alerts

1. Phone shows a **local notification** when day-status mode/morning fingerprint changes
   (or when mobile-alerts queue drains).
2. Enable **notification mirror** in the Zepp phone app so the watch shows the same alert.
3. Wrist mini-program (`packages/calt-zepp` 3.2+) also fires Zepp OS notifications for
   Bible/plan / mode changes after Sync.

## Limits

See `docs/superpowers/specs/2026-08-04-amazfit-android-tracker-bridge-design.md`.
