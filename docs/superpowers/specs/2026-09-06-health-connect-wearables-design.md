# Health Connect → CALT (no ZeppBridge fork)

**Date:** 2026-09-06  
**Status:** Implemented (backend + Android hook + status UI)

## Decision

Do **not** clone [ZeppBridge](https://github.com/lingcang728/ZeppBridge) or scrape Zepp cloud.
Keep **CALT Sync** for on-wrist dumps (richest watch-local sensors). Add **Health Connect** as
the phone hub path so Zepp/Google Fit data that already lands in HC can reach the PC.

```text
Watch → Zepp app → Health Connect (phone) → CALT Android → POST /api/wearables/zepp
Watch → CALT Sync mini-program → hub :8765 → same ingest
Optional: bridge_export JSON (ZeppBridge export file) → same coerce → same DB
```

Single sink: `wearable_daily.payload_json` + Life Tracker / hub readings.

## What shipped

1. `backend/wearables/health_connect_map.py` — HC records + bridge `daily` export → dump shape;
   `inventory_categories()` for raw category presence (never fabricates zeros).
2. Ingest accepts sources: `health_connect`, `hc`, `google_fit`, `bridge_export`, `zeppbridge`
   (plus existing mini_program / zepp / amazfit) and **writes Life Tracker**.
3. Extra categories preserved in payload: `hrv`, `respiratory`, `workouts`, `active_minutes`,
   `vo2max`, `temperature`, … Hub readings added for hrv / temperature / active / respiratory
   when present.
4. `GET /api/wearables/zepp/status` returns `categories`.
5. Android `lib/healthSync.ts` + Tracker **Sync Health Connect** button (native module after
   `expo prebuild` + `react-native-health-connect`; Expo Go shows a clear fallback message).

## Dial-down

| Drop | Keep |
|------|------|
| Own Zepp cloud login | CALT Sync dump/send |
| ZeppBridge dependency | `wearable_daily` + ingest key |

## Verify

```bat
.venv\Scripts\python.exe -m pytest tests/test_health_connect_map.py tests/test_wearables_zepp.py -q
```

On phone (APK): enable Zepp → Health Connect sharing → Sync Health Connect.  
On watch: Dump today → Send queue still works unchanged.
