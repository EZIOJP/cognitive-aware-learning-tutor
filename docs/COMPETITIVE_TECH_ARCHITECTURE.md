# Competitive tech architecture — how they build it

Last updated: 2026-08-18  
Companion to [`COMPETITIVE_LANDSCAPE.md`](./COMPETITIVE_LANDSCAPE.md)

This doc explains **how** competitors implement tracking, blocking, planning, and user communication — libraries, OS APIs, data flow, and UI patterns — and maps the same layers in CALT.

---

## Universal pipeline (every serious product)

```text
┌─────────────┐   ┌──────────────�   ┌─────────────┐   ┌──────────────┐   ┌─────────────┐
│  CAPTURE    │ → │   STORE      │ → │  CLASSIFY   │ → │   SCORE      │ → │  RENDER      │
│  OS / ext   │   │  local/cloud │   │  rules + ML │   │  pulse/goals │   │  web / tray  │
└─────────────┘   └──────────────┘   └─────────────┘   └──────────────┘   └─────────────┘
                                                                    ↓
                                                            ┌──────────────┐
                                                            │    COACH     │
                                                            │ toast/assist │
                                                            └──────────────┘
```

---

## Layer 1 — Capture (foreground / browser)

### RescueTime

| Piece | Implementation |
|-------|------------------|
| **Desktop** | Native agent; polls **foreground window** (app + title) |
| **Windows** | Admin install for full browser title/URL; Win32-style APIs |
| **macOS** | **Accessibility** (window titles) + **Automation** (per-browser AppleScript) |
| **Firefox macOS** | Requires **browser extension** + desktop app (avoid double count) |
| **Idle** | 5 min no input → stop logging (thinking gap &lt; 5 min continues) |
| **Sync** | Local agent → **RescueTime cloud** every few minutes |
| **Privacy** | No keystrokes; URLs trimmed (query strings dropped) |

**Libraries (inferred):** platform-native (Objective-C/Swift on Mac, C++/C# on Windows), not Electron for core agent.

### Rize

| Piece | Implementation |
|-------|------------------|
| **Desktop** | **Native** Mac/Windows tray app (&lt;1% CPU claimed) |
| **Foreground** | Windows **Accessibility API**; macOS accessibility |
| **Node path** | Public fork **`@rize-io/active-win`** (from `active-win`) — native addon returns title, pid, bounds, **browser URL on Mac** |
| **Sessions** | App derives Focus / Meeting / Break from activity + calendar |
| **Sync** | Cloud for AI tagging + team dashboards |

### ActivityWatch (open source — readable code)

| Piece | Implementation |
|-------|------------------|
| **Watchers** | Separate processes: `aw-watcher-window`, `aw-watcher-afk`, `aw-watcher-web` |
| **Windows** | `win32gui.GetForegroundWindow()`, `GetWindowText`, `win32process` + **WMI fallback** for elevated apps |
| **AFK** | Separate watcher: keyboard/mouse idle → `status: not-afk` |
| **Browser** | Chrome/Firefox extensions → URL events |
| **Store** | Local **SQLite** buckets; **REST API** (`aw-server`) |
| **Poll** | ~1s heartbeat loop; merge AFK ∩ window in query layer |

### Freedom (blocking, not full tracking)

| Piece | Implementation |
|-------|------------------|
| **Mac default** | **Local HTTP proxy** port **7769**, regex pass/block |
| **Mac alt** | **Local VPN** / DNS intercept (system-wide) |
| **Chrome** | Extension second layer |
| **Desktop apps** | Hide/minimize blocked apps (Mac); list from installed apps scan |
| **Locked session** | Cannot end early; re-enables VPN/extension if user disables |

### CALT (this repo)

| Piece | Implementation |
|-------|------------------|
| **Desktop** | `tracker_service.py` poll loop, `tracker_win32.py` |
| **Win32 API** | `ctypes` → `user32.GetForegroundWindow`, `GetWindowTextW`, `GetWindowThreadProcessId` + **`psutil.Process(pid).name()`** |
| **Browser** | `selftracker-extension/telemetry.js` — tab URL/title, ~90s cadence, idle backoff 180s |
| **Idle** | `tracker_idle.py` → flush session at `idle_threshold_s` |
| **Store** | Local SQLite + CSV (`tracker_storage.py`) → `TrackedSession` via bridge |
| **Sync** | **Local only** — FastAPI `:8000`, no cloud |

**Gap vs AW:** no WMI fallback for admin processes; no separate AFK bucket in queries.

---

## Layer 2 — Classify & score

### RescueTime

```text
activity_key = hash(app | url | title context)
  → productivity_level: Focus | Other | Neutral | Personal | Distracting
  → category: Communication, Software Development, …
  → Productivity Pulse = weighted average (100/75/50/25/0)
```

- Default taxonomy in **cloud DB**; user overrides per activity
- **Uncategorized** → Neutral (pulls Pulse toward 50) — drives "Sort uncategorized" UX

### Rize

- **AI layer** on top of metadata: client/project tags from title, URL, calendar, past entries
- **Focus Quality Score**: 20+ features (context switches during focus session, etc.)
- User feedback retrains suggestions ("this was Client X")

### Sunsama / Motion / Reclaim

- **No** deep app classification — tasks have **duration + priority + calendar slot**
- "Score" = plan feasibility (planned min vs capacity) or calendar defense %

### CALT

| File | Role |
|------|------|
| `tracker_classify.py` | Regex rules: exe/title → category |
| `domain_classify.py` | Site-specific (YouTube, LeetCode, …) |
| `category_scores.py` | Category → 0–95; **productive if ≥ 60** |
| `productivity_policy.py` | Block lists, overrides |
| `classification_service.py` | **Ollama/LM Studio** for unknowns → pending review |
| `day_metrics.py` | **On-plan** productive only counts for adherence |
| `stats_aggregate.py` | Roll up apps vs sites for dashboard |

**Gap:** no single Pulse formula; no ML project tagging; no focus-quality subscore.

---

## Layer 3 — Block / enforce

### RescueTime Focus Session

- Blocks **Personal/Distracting** categories during session
- User-triggered or **alert-triggered**

### Freedom

- Blocklists + schedules; **Locked Mode**; allow-only whitelist sessions

### CALT

| Layer | Tech |
|-------|------|
| **Browser** | MV3 **`declarativeNetRequest`** dynamic rules (`calt-gate-extension/service_worker.js`) |
| **Policy** | `browser_gate_policy.py` — study/free/bible modes, domain lists |
| **Desktop** | `distraction_gate.py` → kill gaming exes (`tracker_service` listens) |
| **Soft warn** | `content_score.js` keyword scoring on page |
| **Alerts** | `gate_alerts.py` → queue → **edge-tts / Piper / SAPI** |

**Advantage:** DNR + process kill + plan context; stronger than RescueTime for games.

---

## Layer 4 — Store & API

| Product | Primary store | Client API |
|---------|---------------|------------|
| RescueTime | Cloud | Web app + desktop agent HTTPS |
| Rize | Cloud | Electron/native → REST |
| ActivityWatch | Local SQLite | REST `aw-server` |
| Sunsama/Motion | Cloud Postgres | GraphQL/REST SPA |
| **CALT** | SQLite (`vocab_app.db`, tracker local DB) | FastAPI `/api/behavior/*`, `/api/planner/*` |

CALT ingest paths:
- Desktop → events → `tracker_bridge` → `TrackedSession`
- Extension → WebSocket / POST telemetry
- Wearables → `/api/wearables/zepp` → `wearable_daily`

---

## Layer 5 — Render (UI patterns)

### RescueTime

- **Web dashboard** (React-class SPA): Activities columns, goals progress bars, weekly email HTML
- **Assistant** (desktop): live goal bar + notifications (native OS notifications)
- **Reports:** productivity level stacked bars, top apps list, trends

### Rize

- **Day calendar** with pending entry review panel docked beside timeline
- **Focus timer overlay** during session
- **Tray menu** quick stats

### Sunsama

- **Guided wizard** (multi-step modal): yesterday → pick tasks → estimate → capacity warning → timebox
- **Shutdown wizard:** review → carry forward
- Calendar + task list split view

### CALT

| UI | Pattern | Files |
|----|---------|-------|
| **GlanceBar** | Horizontal KPI strip + SVG score ring | `GlanceBar.tsx` |
| **DayRibbon** | 24h plan vs actual + sleep clip | `DayRibbon.tsx`, `planVsActualUtils.ts` |
| **Heatmap** | 7-day adherence cells | `WeeklyAdherenceHeatmap.tsx` |
| **Focus rhythm** | Bar chart in-zone / drift | `FocusRhythmPanel.tsx` |
| **Tray** | pystray menu — today min, plan, gate | `tracker_tray.py` |
| **Block popup** | Tkinter when exe killed | `tracker_block_gui.py` |
| **Classification** | Approve/reject LLM suggestions | `ClassificationReview.tsx` |

**Stack:** React 18 + Vite + Tailwind + Recharts; no separate native dashboard app.

**Gap:** no desktop Assistant window; no guided multi-step ritual UI; no ranked Activities page.

---

## Layer 6 — Coach (talk to user)

| Product | Channel | Logic | Trigger |
|---------|---------|-------|---------|
| **RescueTime** | OS notification + Assistant UI | Goal progress %; alert once on threshold | Real-time category/app limits |
| **Rize** | Distraction blocker popup + nudges | Context-switch pattern detection | During focus session |
| **Freedom** | Block page | Static "you're blocked" | DNS/proxy hit |
| **Whoop** | App push + haptic | Recovery → strain target | Morning + during workout |
| **CALT** | TTS Jarvis + extension lock page | Canned `block_dialogues`; gate poll 4s | Gate mode, block event, mobile queue |

CALT flow:
```text
extension gate_policy.js --poll--> GET /distraction-gate
       ↓ block
POST /gate-alert → pending_gate_alerts.json
       ↓
tracker_service drains → speak_alert() → edge-tts
```

**Gap:** no goal progress notifications; no "30m YouTube" threshold coach.

---

## Wear OS / health (Zepp path — CALT specific)

Competitors mostly **don't** merge wearables into productivity UI. CALT:

```text
Watch (Zepp OS 6) sensors.js → queue.js BLE chunks
  → Phone Side Service fetch → POST /api/wearables/zepp
  → day_stamp.py + ingest_service.py
  → hub rollup + DayRibbon sleep clip
```

Libraries: Zepp `@zos/*`, phone `@zos/ble`, PC FastAPI + Pydantic.

---

## Platform API cheat sheet (if we borrow)

| Need | Windows | macOS | Browser |
|------|---------|-------|---------|
| Foreground window | `GetForegroundWindow` (CALT: ctypes) | Accessibility API | N/A |
| Process name | psutil / WMI (AW) | NSWorkspace | N/A |
| Browser URL | Extension `tabs` API | Extension + Automation | MV3 |
| Block sites | DNR (CALT) | Proxy/VPN (Freedom) | DNR |
| Kill app | `TerminateProcess` / shell | `NSRunningApplication` | N/A |
| Idle | `GetLastInputInfo` | `CGEventSourceSecondsSinceLastEventType` | `idle` API |
| Local health hub | Health Connect (Android) | HealthKit (iOS) | N/A |

---

## CALT weak points (technical)

1. **Single poll loop** — no watcher plugin architecture (AW model)
2. **No cloud sync** — single machine only
3. **Classification** — rules + optional LLM; no continuous learning loop like Rize
4. **No native coach UI** — TTS only, no Assistant panel with goal bars
5. **Extension split** — SelfTracker + Gate two extensions (RescueTime merges agent)
6. **Render** — rich web UI but no email/weekly narrative generator
7. **macOS/Linux** — no `tracker_win32` equivalent

---

## What to implement first (technical)

1. **`productivity_pulse.py`** — RescueTime weights on `stats_aggregate` output
2. **`goals_alerts.py`** — threshold engine on rolling session sums → tray + optional DNR mode flip
3. **Activities API** — `GET /api/behavior/activities?range=week` from `TrackedSession` GROUP BY site/exe
4. **Away prompt** — hook `flush_current("idle")` → optional Tk toast / hub notification
5. **WMI fallback** — port AW pattern into `tracker_win32.py` for admin apps
