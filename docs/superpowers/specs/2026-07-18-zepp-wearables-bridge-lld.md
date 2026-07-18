# LLD — Zepp Wearables Bridge (CALT)

**Date:** 2026-07-18  
**Status:** Draft  
**Requirements:** [2026-07-18-zepp-wearables-requirements.md](./2026-07-18-zepp-wearables-requirements.md)  
**ADR:** [ADR-002-zepp-ingest-hybrid.md](../../decisions/ADR-002-zepp-ingest-hybrid.md)

---

## 1. Decision summary

| Choice | Decision |
|--------|----------|
| Client on watch | **Zepp OS Mini Program** (not a separate Amazfit native app) |
| Custom watchface | **No** — cannot `fetch` CALT or show our plans (system data_type only). Use **SecondaryWidget / Shortcut** for glance instead |
| HTTP from | **Side Service** on phone (`fetch` over Wi‑Fi/LAN to CALT) |
| Auto sync | Side Service interval + manual Sync + optional App Service on sleep/wake events |
| Data type | **Processed** daily summaries |
| Server | Custom CALT `POST /api/wearables/zepp` + `GET …/plans` |
| Calendar / Google | **None** — planner stays in CALT; phone notifies from planner |
| Notifications | **CALT phone** primary; watch `@zos/notification` / agenda refresh on sync |

**Doc checklist:** [2026-07-18-zepp-os-implementation-from-docs.md](./2026-07-18-zepp-os-implementation-from-docs.md)

---

## 2. System context

```text
┌─────────────────┐     BLE      ┌──────────────────────┐
│ Amazfit watch   │◄────────────►│ Phone Zepp app       │
│ Device App      │              │ Side Service (fetch) │
│ Sleep + agenda  │              │ Settings (base_url)  │
│ plan cache      │              │ sync cycle timer     │
└─────────────────┘              └──────────┬───────────┘
                                            │ Wi‑Fi / LAN
                                            ▼
                                 ┌──────────────────────┐
                                 │ CALT custom endpoint │
                                 │ POST /wearables/zepp │  ← dump health
                                 │ GET  /wearables/zepp │
                                 │      /plans          │  ← active plans
                                 └──────────┬───────────┘
                                            │
              ┌─────────────────────────────┼─────────────────────────────┐
              ▼                             ▼                             ▼
     Life Tracker sleep              Planner blocks                 CALT phone app
                                     (source of truth)              local notifications
```

**Sync cycle (whenever possible):** POST health → GET plans → update watch cache/UI.  
**No Google Calendar** in this design.

---

## 3. Mini Program structure (Zeus)

```text
calt-zepp/
  app.json                 # permissions: data:user.hd.sleep, heart_rate
  app.js
  page/                    # Device App UI — Sync, last status
  app-side/                # Side Service — messaging + fetch
  setting/                 # Settings App — base_url, token, interval_min
  shared/                  # message.js / ZML helpers
```

### 3.1 Device App responsibilities
- `Sleep.updateInfo()` then `getInfo()` / `getStage()` / `getNap()` as available
- Optional: `HeartRate.getLast()`, `getResting()` — no continuous HR by default
- UI: Sync now, last health sync, **active plans agenda** (from cache)
- On sync request: `messageBuilder.request({ method: 'SYNC_ALL', params: { healthSnapshot } })`
- On sync response: persist `plans[]` to device storage; redraw agenda
- Show stale banner if plans older than `2 * interval_min`

### 3.2 Side Service responsibilities
- Listen for `SYNC_ALL` (and timer tick)
- Read Settings: `base_url`, `ingest_token`, `interval_min`, `plan_horizon_hours`
- **Whenever possible (full cycle):**
  1. `POST ${base_url}/api/wearables/zepp` with health body (skip body if empty/unchanged optional)
  2. `GET  ${base_url}/api/wearables/zepp/plans?horizon_hours=…`
  3. Return `{ healthOk, plans, plansFetchedAt, errors[] }` to Device App
- Timer: run SYNC_ALL while Side Service alive
- Partial success allowed (plans update even if POST fails)

### 3.3 Settings App
- `base_url` (e.g. `http://192.168.1.42:8000`) — never `localhost`
- `ingest_token`
- `interval_min` (default 15)
- `plan_horizon_hours` (default 24)
- `prefer_morning_sync` toggle

### 3.4 Why Mini Program beats a separate phone app
- Official sensor APIs and permissions
- Side Service already has `fetch` + BLE bridge
- Ships with Zepp pairing you already use
- Separate native app would reinvent BLE against undocumented stacks

---

## 4. CALT backend

### 4.1 Endpoint

`POST /api/wearables/zepp`

Headers: `Authorization: Bearer <INGEST_TOKEN>` or `X-CALT-Wearable-Key`

Body (schema 1):

```json
{
  "schema": 1,
  "source": "mini_program",
  "device": { "model": "t-rex", "os": "5" },
  "captured_at": "2026-07-18T07:12:00+05:30",
  "local_date": "2026-07-18",
  "sleep": {
    "score": 82,
    "total_min": 410,
    "deep_min": 95,
    "start_min": 23,
    "end_min": 433,
    "stages": [{ "model": 1, "start": 23, "stop": 90 }]
  },
  "heart": { "last": 62, "resting": 54 },
  "activity": { "steps": 1200 },
  "meta": {}
}
```

Response: `{ "ok": true, "upserted": "sleep", "local_date": "..." }`

### 4.1b Plans pull

`GET /api/wearables/zepp/plans?horizon_hours=24`

Same auth as ingest (Bearer ingest key) for Mini Program simplicity in v1  
(or user-scoped JWT later).

Response:

```json
{
  "schema": 1,
  "generated_at": "2026-07-18T10:00:00+05:30",
  "plans": [
    {
      "id": 123,
      "title": "Scaler — daily lessons",
      "category": "Coursework (Browser)",
      "start_at": "2026-07-18T10:30:00+05:30",
      "end_at": "2026-07-18T11:20:00+05:30",
      "status": "scheduled",
      "source": "study"
    }
  ]
}
```

Rules: local “now” window = start of today → now + horizon (or end of day); exclude `cancelled` / `done` unless `include_done=1`; order by `start_at`.

### 4.2 Modules (proposed)

| Path | Role |
|------|------|
| `backend/wearables/router.py` | HTTP routes |
| `backend/wearables/schemas.py` | Pydantic models |
| `backend/wearables/normalize.py` | Map sleep → hours/quality; clamp |
| `backend/wearables/ingest.py` | Upsert into hub/life sleep storage |
| `backend/wearables/auth.py` | Shared key check (env `WEARABLES_INGEST_KEY`) |

Reuse existing Life Tracker / hub sleep fields; **no parallel sleep DB** unless schema forces it (Alembic only if needed).

### 4.3 Mapping rules

| Zepp | CALT |
|------|------|
| `total_min / 60` | `sleep_hours` |
| `score` 0–100 → map 1–5 | `sleep_quality` (e.g. score/20 clamped) |
| `start_min` / `end_min` | optional bedtime/wake if columns exist |
| missing sleep | 204 / skip sleep upsert; still store heart if present |

### 4.4 Planner hook (P4)

In `llm_propose._adherence_load_scale` (or sibling `_sleep_load_scale`):

- If yesterday `sleep_hours` &lt; 6 or score &lt; 60 → multiply target by 0.85–0.9
- Compose with adherence scale (take min of scales)
- Rationale string mentions sleep soft

---

## 5. Optional cloud sidecar (P3)

Copy **pulsebridge** pattern only:

```text
HAR → config token → sync loop → POST same /api/wearables/zepp
  source: "cloud_sidecar"
```

- Windows: Task Scheduler or Huey job later; Linux: systemd timer
- Do not import fragile client into FastAPI process — keep sidecar process separate
- Same normalizer on server so cloud blobs don’t leak into UI

Processed cloud extras (HRV, PAI): store in `meta` or future `wearable_daily` table; v1 may ignore beyond sleep.

---

## 6. Automatic sync reliability

| Mechanism | Reliability | Notes |
|-----------|-------------|--------|
| Side Service timer | Medium | Dies if Zepp killed / phone sleep policies |
| Manual Sync on watch | High | User fallback |
| System events (sleep exit) | Medium+ | Use if API_LEVEL supports sleep-mode events |
| Cloud sidecar timer | High for daily batch | Token refresh every ~30d |
| Hybrid | Best | Sidecar overnight + Mini Program when wearing/phone up |

**LLD rule:** Never rely on watch→PC direct Wi‑Fi alone; always phone Side Service or PC sidecar.

---

## 7. Processed vs raw

```text
Firmware / Zepp cloud
    → already processed summaries (score, stages, resting HR)
        → Mini Program / sidecar
            → CALT normalize (hours, quality band)
                → optional analytics scores (recovery) later
```

Do **not** ingest continuous HR arrays in v1.

---

## 8. Security

- `WEARABLES_INGEST_KEY` required in production/dev when wearables enabled
- Reject missing/invalid key with 401
- Bind recommendation: LAN only; document Tailscale for remote
- No logging of full tokens

---

## 9. Notifications (CALT phone) + watch agenda

### 9.1 Phone (primary)
- CALT Android / PWA reads upcoming `PlannerBlock` rows for the local user.
- Schedule OS local notifications: `start_at - lead_minutes` (default 10).
- Payload: title, category, deep link to Today / Plan.
- Reschedule on planner apply / edit / delete.
- **Does not** sync to Google or Amazfit system calendar.

### 9.2 Watch active plans (required on sync)
- Every Side Service sync cycle calls `GET /api/wearables/zepp/plans`.
- Device App replaces agenda cache; list next blocks on home page of Mini Program.
- After user applies/edits plan on PC, watch picks it up on next interval or manual Sync (“whenever possible”).
- Alerts: phone-first in P4; watch buzz only if trivial with Zepp APIs.

### 9.3 Explicit
- No Google Calendar OAuth, push, or busy import in this feature set.

---

## 10. Test plan

| Test | Expect |
|------|--------|
| Unit normalize | 410 min → 6.83h; score 82 → quality ≥ 4 |
| Ingest upsert | Second POST same `local_date` updates, count=1 |
| Auth | Wrong key → 401 |
| Mini Program dry-run | Side Service POST to mock server |
| Planner | Low sleep fixture softens target |

---

## 11. File touch list (implementation)

```text
docs/superpowers/specs/2026-07-18-zepp-wearables-*.md   (done)
docs/decisions/ADR-002-zepp-ingest-hybrid.md             (done)
backend/wearables/*                                      (P1)
backend/main.py                                          mount router
src/... Life Tracker / settings bits                     (P1)
calt-zepp/ or packages/zepp-miniapp/                     (P2, new Zeus project)
scripts/wearables_sidecar/ (optional, pulsebridge-inspired) (P3)
```

---

## 12. Explicit non-goals in this LLD

- Google Calendar sync (user rejected)  
- Amazfit native calendar CRUD  
- HA dependency  
- Publishing to Zepp Store (personal sideload first)  
