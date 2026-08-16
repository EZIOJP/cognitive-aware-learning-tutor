# CALT Productivity System — How It Works

Companion data snapshot: [`data/exports/productivity_snapshot_2026-08-09.json`](../data/exports/productivity_snapshot_2026-08-09.json)  
(Regenerate anytime: `python scripts/export_productivity_snapshot.py`)

---

## What “productivity” means here

CALT scores **wall-clock time** spent in apps/sites against a **category score map** and a **daily goal** (default 240 productive minutes). Games stay locked until the goal is met (plus Bible morning rules).

| Layer | Role |
|-------|------|
| **Plan** | Planned blocks (`planner_blocks`) — routines, meals, study, free |
| **Actual** | Tracked sessions (`tracked_sessions`) — desktop + Edge extension (active tab) + CALT SPA productive lanes |
| **Sleep** | Amazfit/Zepp (`wearable_daily`) — overwrites PC-on-during-sleep for display + gate |
| **Gate** | `GET /api/behavior/distraction-gate` — productive minutes, browser mode, morning unlock |

---

## How data is collected

```text
Desktop tracker (exe + window title)
        │  SESSION_END → ws / ingest → tracked_sessions (source=desktop_tracker)
        ▼
Edge SelfTracker extension (URL + title + domain)
        │  SESSION_END batch → tracked_sessions (source=extension)
        │  Active focused tab only; skips localhost (CALT SPA)
        │  Server reclassifies URL (Scaler → Coursework, etc.)
        ▼
CALT web / iPad (study-presence)
        │  Productive lanes only, tab visible + focused:
        │    Lecture Notes (doc open + reading)
        │    /review (quiz) · /gre-vocab · /math-tutor
        │  Bible = spiritual (not productive SPA credit)
        │  Other CALT routes ignored
        ▼
Zepp Mini Program
        │  sleep start_min/end_min + naps → wearable_daily
        ▼
Distraction gate / hub rollup / calendar overlay
        │  Union productive intervals; subtract sleep; clip Cursor under sleep
```

### Sources on `tracked_sessions`

| `source` | Comes from | Typical `app_name` |
|----------|------------|--------------------|
| `desktop_tracker` | Local desktop agent | `Cursor.exe`, games (not Edge — see below) |
| `extension` | Edge SelfTracker | domain e.g. `scaler.com` |
| `calt_spa` | Productive SPA heartbeat (notes / quiz / vocab / math) | `calt_spa:web` / `calt_spa:ipad` |
| (overlay only) `wearable_sleep` | Not stored as tracked row; injected in planner overlay | Amazfit |

**Edge ownership:** Desktop tracker **ignores** `msedge.exe` / WebView helpers (`tracker_ignore`). Only the Edge SelfTracker extension should create browser sessions. Chrome/Firefox still appear on desktop (gate / unauthorized-browser path).

### Classification

1. Desktop: exe + title rules / cache → category  
2. Extension: **URL/domain first** (`domain_classify`) → Coursework / Study / Social / …  
3. Policy overrides + optional LLM cache  
4. Score from `category_scores` (threshold usually **60**)  
5. Sleep overlap → non-productive (`sleep_overwrite` stamp + live subtract)

### Sleep rules (important)

- Zepp minutes are from sleep **onset** day; naps with large offsets (≥1440) are dual-anchored to wake day.  
- Overnight paints **evening on bed day**, **morning on wake day** (no fake “tonight” wrap).  
- PC left on as Cursor/idle during sleep is **clipped** on calendar and **excluded** from productive minutes.

---

## Formats you can export

### A) Built-in Week export (Settings → Week export)

```http
GET /api/planner/export/last-7-days?days=7&format=json
GET /api/planner/export/last-7-days?days=7&format=csv
```

UI: Productivity → **Settings** → Week export (JSON / CSV).

**JSON shape (high level):**

```json
{
  "export_version": "...",
  "exported_at": "ISO-8601",
  "purpose": "timetable / AI propose context",
  "range": { "start": "YYYY-MM-DD", "end": "YYYY-MM-DD", "days": 7 },
  "policy_snapshot": { "threshold": 60, "daily_goal_minutes": 240, "...": "..." },
  "summary": {
    "total_tracked_minutes": 0,
    "total_productive_minutes": 0,
    "peak_hours": [14, 15, 10],
    "...": "..."
  },
  "weekday_patterns": { "mon": { "avg_productive_minutes": 0, "avg_hour_minutes": [/*24*/] } },
  "suggested_timetable_hints": [],
  "by_day": [
    {
      "date": "YYYY-MM-DD",
      "planned_minutes": 0,
      "actual_minutes": 0,
      "productive_minutes": 0,
      "adherence_pct": 0,
      "planned_blocks": [/* planner blocks */],
      "by_category_minutes": { "IDE / Code Editor": 120 },
      "by_hour_minutes": { "0": 0, "1": 0, "...": "..." },
      "top_apps": [{ "app": "Cursor.exe", "minutes": 90 }]
    }
  ]
}
```

**CSV:** flattened day / category / hour rows for spreadsheets.

### B) Snapshot package (this doc’s companion)

File: `data/exports/productivity_snapshot_YYYY-MM-DD.json`

Includes:

- `full_week_export` — same payload as week export (last 3 days in the sample)  
- `sample_tracked_sessions` — up to 40 raw sessions per day (today / yesterday / day-before)  
- `sleep` — wearable hours + resolved bouts  
- `distraction_gate_today` — live productive minutes / browser mode  

---

## Sample from your machine (Aug 4–6, 2026)

Pulled into the snapshot at export time (IST). Summary:

| Day | Planned | Actual (tracked) | Productive | Sessions (export count) |
|-----|---------|------------------|------------|-------------------------|
| 2026-08-04 | ~100m | ~871m | ~206m | 609 |
| 2026-08-05 | (see JSON) | (see JSON) | (see JSON) | (see JSON) |
| 2026-08-06 | (see JSON) | early day | gate ~3m at export | (see JSON) |

**Gate at export:** productive **3** min · goal **240** · browser mode **study** · unlocked **false**.

**Sleep (Aug 5 example, after smart sleep fix):** overnight ~18:51→01:13 + morning nap + evening ~17:48→23:04; PC under those windows should show as Sleep, not Cursor.

Open the JSON for full `by_day`, `top_apps`, session samples, and sleep bouts.

---

## APIs used by the Productivity UI

| Surface | Endpoint |
|---------|----------|
| Calendar plan blocks | `GET/POST /api/planner/blocks` |
| Actual overlay + hour slices | `GET /api/planner/overlay/actual?from=&to=` |
| Desktop / browser stats | `/api/behavior/desktop-stats`, `browser-stats`, timeline |
| Hard-block / morning / mode | `GET /api/behavior/distraction-gate` |
| Study presence (notes / quiz / vocab / math) | `POST /api/behavior/study-presence` |
| Reclassify / sleep stamp | `POST /api/behavior/reclassify-today` · `scripts/reclassify_today.py` |
| Wearables | `POST /api/wearables` |
| Week export | `GET /api/planner/export/last-7-days` |

---

## Plan tab flow (UI)

1. **Routines** — fixed daily times  
2. **Goals** — focus hours / text for AI  
3. **Build** — propose draft week  
4. **Apply** — write drafts to calendar  
5. **Watch** — Google Calendar → Amazfit  

Morning confirm + browser STUDY mode live under “Morning confirm & browser mode”.

---

## Privacy note

Snapshots under `data/exports/` can contain window titles and domains. Do not commit them if the repo is shared; they are listed in the same spirit as local `data/` logs.
