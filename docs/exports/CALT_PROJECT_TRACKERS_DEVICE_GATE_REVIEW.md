# CALT — Project + Trackers + Device Gate (review export)

**Exported:** 2026-08-19  
**Purpose:** One file to review how the local study/productivity system works today, what each tracker collects, how pieces connect, and the proposed Flutter + native phone lock.  
**Not a commit of new product code.** Device Gate is design-only until you reopen that lane.

**Canonical in-repo copies:**

| Doc | Role |
|-----|------|
| This file | Standalone review export |
| `docs/superpowers/specs/2026-08-19-mobile-device-gate-design.md` | Short Device Gate spec |
| `docs/superpowers/plans/2026-08-19-mobile-device-gate.md` | Build phases |
| `docs/PRODUCTIVITY_SYSTEM.md` | Plan vs actual + gate scoring |
| `docs/CALT_SYNC_MANUAL_DUMP.md` | Watch health dump |

---

## 1. What this project is

**Cognitive-Aware Learning Tutor (CALT)** is a **local-first personal system** on your Windows PC:

1. **Study** — lecture notes → quiz → Review Hub (FSRS). GRE vocab cycle. Math drills. One quiz engine (`/api/quiz`).
2. **Day rules** — morning Bible + confirm plan, then **study mode**. Games / distraction stay gated until **daily productive minutes** (default ~240) are earned.
3. **Truth about time** — desktop apps + Edge tabs + (optionally) CALT web study lanes written into SQLite `tracked_sessions`.
4. **Body** — Amazfit watch **manual dump** of today’s sensors into `wearable_daily` (sleep clips fake “Cursor at 3am”).
5. **Life** — Life Tracker / hub readings fed from wearables + mapped fields.

**Stack (PC):** React (Vite) `:5173` → FastAPI `backend.main` `:8000` → SQLite `data/vocab_app.db`.  
**LAN hub:** desktop tracker also serves `:8765` so the watch/phone can hit wearables + `day-status` when the full web stack is up or the hub is running in-process.

**Daily start:** `run.bat` (API + frontend). Desktop tracker is a **separate** process (tray / `restart_desktop_tracker.bat`). Both matter: no tracker → no Windows app minutes; no API → no web/gate.

**What CALT is not:** a cloud SaaS, a public App Store family-control product, or a full phone OS. EEG/wearables beyond the dump are mostly simulated or out of scope.

---

## 2. Mental model: clock vs sensors vs locks

```text
                    ┌─────────────────────────────────────┐
                    │  PC CALT = CLOCK + LEDGER           │
                    │  SQLite tracked_sessions            │
                    │  distraction-gate + day-status      │
                    │  planner / calendar overlay         │
                    └───────────────┬─────────────────────┘
                                    │ unlocked? remaining minutes?
           ┌────────────────────────┼────────────────────────┐
           ▼                        ▼                        ▼
   Windows lock              Edge lock                 Phone lock (FUTURE)
   desktop tracker           SelfTracker +             Flutter + native
   + hard-block games        CALT Gate extension       overlay / Screen Time
           │                        │                        │
           └────────────┬───────────┴────────────────────────┘
                        ▼
                 Watch (CALT Sync)
                 body dump only — does NOT unlock the day
```

**Rule you asked for (all devices, same idea):**

> Until today’s **productivity is complete** (PC gate), **distraction is blocked**.  
> **Porn stays hard** even after. Other apps may get a **5‑minute rest window** after unlock.

PC already does the first sentence (with morning Bible/plan in front of study mode). Phone/iPad would **subscribe** to that boolean, not compute a second goal.

---

## 3. How a day unlocks today (PC)

Typical sequence (see `GET /api/behavior/distraction-gate` and `GET /api/behavior/day-status` schema 3):

1. **Bible first** (`browser_mode: bible`) — spiritual credit; not the 240m study goal.
2. **Confirm plan** (`planning`) — today’s blocks exist / confirmed.
3. **Study mode** — Edge + desktop gate: productive categories (score ≥ ~60) count toward the goal; games hard-blocked if policy armed.
4. **Unlocked / free** — `hard_block.unlocked` or `day_unlimited` or enough `productive_minutes` vs `daily_goal_minutes`.

`day-status` already exposes for mobile/watch **glance**:

- `morning.*` (bible_done, plan_confirmed, rewards)
- `browser_mode` + labels
- `hard_block`: armed, locked, unlocked, productive / goal / remaining minutes
- `tracker_alive`, wearables last sync, productivity pulse, comms health

**Proposed later:** `device_gate.unlocked` = that same “distraction allowed” bit, named for phones so Flutter does not guess.

---

## 4. Trackers — what each one is for

Think **three collectors + two blockers + one dumper**. They are not interchangeable.

### 4.1 Desktop tracker (Windows)

**Job:** “What program is in the foreground on the PC?”

| Captures | How |
|----------|-----|
| `exe`, window title (short), category, productivity score | Poll ~5s (faster when gate armed) |
| Session slices | End on app switch, idle ~5 min, max ~10 min slice |
| Optional NSFW screen scan | Temp screenshot, score, file deleted |
| Hard-block | Kill/soft-lock games when policy armed and day not unlocked |

**Does not capture:** Edge URLs (Edge is ignored on purpose — `tracker_ignore`). Keystrokes, clipboard, mic.

**Stored:** `tracked_sessions` (`source=desktop_tracker`) + CSV under `data/logs/`.  
**Used for:** calendar actuals, productive minutes, game lock.

**Process:** tray app / `backend/behavior/tracker_service.py`. Hub `:8765` is **HTTP for watch/phone**, not the session log itself.

### 4.2 SelfTracker extension (Edge — tracking)

**Job:** “What website is focused in Edge?”

| Stream | What |
|--------|------|
| Active-tab sessions | URL, title, domain, category, duration → **minutes** |
| Light telemetry | Extra tabs / recent history → **log files**, not the goal clock |
| Deep scrape (~30s) | Scroll/YouTube % → events, not the main ledger |
| Gate alerts | Short URL for TTS |

Skips `chrome://`, extensions, **localhost** (so the CALT SPA is not double-counted as “browsing”).

**Stored:** `tracked_sessions` (`source=extension`). Server may reclassify domain (e.g. Scaler → Coursework).

### 4.3 CALT Gate extension (Edge — blocking)

**Job:** “Stop this tab.” **Not** a tracker.

- Polls `GET /api/behavior/distraction-gate`
- DNR / soft-land / `locked.html`
- Local content-score (page text **not** uploaded)
- Posts short `gate-alert`

No `tracked_sessions` from Gate.

### 4.4 CALT web study-presence

When you actually study in the SPA (notes reading, `/review`, GRE, math) with the tab focused: `source=calt_spa`. Bible in the web app is **spiritual**, not productive SPA minutes.

### 4.5 CALT Sync (Amazfit / Zepp) — dumper, not a tracker of apps

**Job:** Dump **body** metrics the watch OS exposes **today**. Queue up to 7 days you previously dumped. No plans, no PC lock, no YouTube block.

Typical payload: sleep (stages/naps), HR, steps, calories, distance, SpO₂, stress, PAI, stand, fat burn, battery, temperature **only if firmware has it**.

**Path:** Watch → phone Side Service → `POST /api/wearables/zepp` on **`:8765`**. PC merges into `wearable_daily` (idempotent chunks). Sleep **overwrites** “PC was on all night” on the calendar.

Watch **does not** decide unlock.

### 4.6 Expo Android tracker (`packages/calt-android-tracker`)

**Job today:** Checklist + notify + arm/disarm **via JWT**. Glance at `day-status`. **Not** an overlay over YouTube.

### 4.7 What is never collected (on purpose)

Passwords, full page HTML to server, persistent screenshots, inventing watch history, Edge titles via desktop tracker.

---

## 5. How minutes become “productive”

```text
SESSION_END (desktop or extension or SPA)
    → classify (exe/title or URL/domain)
    → category_scores (threshold ~60)
    → subtract sleep windows from watch
    → productive_minutes vs daily_goal
    → gate locked / unlocked
```

**Plan vs actual:** `planner_blocks` (intent) vs `tracked_sessions` (what happened). Calendar paints both; sleep clips overnight.

**Export already in product:** Productivity → Settings → week JSON/CSV (`GET /api/planner/export/last-7-days`).

---

## 6. How all processes sit on one machine

```text
run.bat                 Vite :5173 + uvicorn :8000
Desktop tracker tray    poll windows + optional hub :8765
Edge                    SelfTracker (time) + CALT Gate (block)
Phone on Wi-Fi          Zepp app (watch BLE → HTTP :8765)
                        Expo tracker (optional glance)
Watch                   CALT Sync Dump/Send only
```

If **tracker is dead**, Windows minutes freeze; Edge can still count sites.  
If **API is dead**, web/gate/JWT fail; hub `:8765` may still take watch dumps if tracker is up.  
If **phone can’t see LAN**, watch dump and future Device Gate poll fail → Device Gate must **fail closed** (stay locked).

---

## 7. Proposed Device Gate (not built)

**Problem:** Phone/iPad distraction is outside the PC gate. Same rule: block until PC says the day is done.

**Split:**

| Layer | Tech | Does |
|-------|------|------|
| Clock | Existing `day-status` | `device_gate.unlocked` (to add) |
| Face | **Flutter** | Minutes left, 5‑min button, permission screens |
| Hands | **Kotlin** Accessibility overlay + optional VPN/DNS | Cover YouTube/games; porn never 5‑min |
| Hands later | **Swift** Family Controls | Same rule, weaker force |

**Two lists:** porn = always hard (DNS + overlay). Distraction apps = blocked until unlock, then optional 5‑min. Allow-list (Maps, CALT) so you are not trapped.

**v1 = Android only.** iOS after the Android APK is in your pocket daily.  
**Not:** Flutter-only blocking, Play Store, iPad as strict as Edge+hosts.

**Phases (see plan file):** 0 PC flag → 1 Flutter poll UI → 2 overlay → 3 DNS → 4 iOS.

**Time (honest):** Android v1 ~1–2 months focused; iOS extra months + Apple entitlement.

---

## 8. Review checklist (for you)

- [ ] PC study loop is “done enough”; Device Gate is a **companion**, not a rewrite.
- [ ] Productive minutes stay **PC-led** for v1 (phone doesn’t add a second goal).
- [ ] Porn never gets the 5‑min window.
- [ ] Expo Android tracker stays glance; new folder for Flutter gate.
- [ ] Fail closed off-LAN unless Tailscale.
- [ ] Watch stays dump-only.
- [ ] First code slice if approved: `device_gate` on `day-status` + pytest — no Flutter until that boolean is right.

---

## 9. File map (orientation)

| Area | Path |
|------|------|
| Web app | `src/` |
| API | `backend/main.py`, `backend/behavior/`, `backend/wearables/` |
| Desktop tracker | `backend/behavior/tracker_service.py`, `tracker_hub.py` |
| Sessions table | `backend/models/timetable.py` (`TrackedSession`) |
| Edge track | `selftracker-extension/` |
| Edge block | `calt-gate-extension/` |
| Watch dump | `packages/calt-zepp/` |
| Phone glance | `packages/calt-android-tracker/` |
| Device Gate (future) | `packages/calt-device-gate/` (not created yet) |

---

## 10. One paragraph you can quote

CALT is a PC-local study and productivity system: notes and quizzes on one side, a daily unlock on the other. Windows programs and Edge tabs write timed sessions; a gate blocks games and sites until Bible, plan, and productive minutes are done; the watch only dumps health. The proposed Flutter app would not be a new tutor — it would ask the PC “are we unlocked yet?” and let native Android (then iOS) hide distraction apps until the answer is yes, with porn always blocked and a short rest window only after unlock.
