# Session Log

Running checklist for Cursor sessions.

**Current focus (2026-08-30):** Math OCR close-out (GPU ONNX, retrain export, stroke_symbol, structure calibrate). Device Gate remains docs-only.

---

## 2026-08-30 — Math OCR close-out

**Done:**
- [x] CUDA ONNX providers (`onnx_providers.py`, `OCR_ONNX_DEVICE`)
- [x] TexTeller retrain export: `retrain_service.py`, `POST /api/math/train/retrain`, `scripts/retrain_texteller.*`
- [x] Stroke-symbol real ink: `train_from_handwriting_dataset`, `POST /api/math/train/retrain-stroke-symbol`
- [x] Structure verify calibration: `structure_calibrate.py`, `POST /api/math/train/recalibrate-structure`
- [x] Export doc: `docs/exports/math-ocr/OCR_CLOSEOUT_2026-08-30.md`
- [x] Build/run guide: `docs/exports/math-ocr/MATH_OCR_BUILD_AND_CHANGES.md`

**Try:** `pip install onnxruntime-gpu` · Train Playground confirm samples · `scripts\retrain_stroke_symbol.bat` · `scripts\recalibrate_structure.bat` · `GET /api/math/ocr/status` · read `docs/exports/math-ocr/MATH_OCR_BUILD_AND_CHANGES.md`

---

## 2026-08-19 — Device Gate docs (Flutter + native)

**Done:**
- [x] Spec: `docs/superpowers/specs/2026-08-19-mobile-device-gate-design.md`
- [x] Plan: `docs/superpowers/plans/2026-08-19-mobile-device-gate.md`

**Not started:** Flutter package, Accessibility overlay, iOS Family Controls.

**Try:** Read spec; reopen lane only when Android lock is the next product.

---


## 2026-08-18 — Local owner profile (drop login)

**Done:**
- [x] Spec: `docs/superpowers/specs/2026-08-18-local-owner-profile-design.md`
- [x] `GET /api/vocab/auth/local-session` + `PATCH /api/vocab/auth/me` (`display_name`)
- [x] Web app auto-binds solo owner on boot; `/login` → `/profile`
- [x] Profile: display name + this-machine API/wearables URLs; no logout onboarding
- [x] README / SETUP: first-run is `run.bat` → `:5173`, not admin password

**Try:** empty localStorage → home loads · Profile save name · `/login` lands on Profile · ranks stay **off** until Profile toggle

---

## 2026-08-18 — Reward-day leftover + heavy poll + notes 500

**Done:**
- [x] Cleared leftover `browser_free_override.json` (12h PIN free until ~21:13) — not a claimed reward day
- [x] Tray **End free time** (no PIN) → `clear_free_override()`
- [x] Tracker poll: no auto Edge kill; comms tick / edge-gone at most every 15s
- [x] Lecture library: skip remaps that collide on `lecture_notes.filename`; tree rolls back IntegrityError

**Try:** Reload http://localhost:5173/lecture-notes · tray End free time if free mode stuck · tracker PIN restart for live lighter poll

---

## 2026-08-18 — Edge close why + comms incident log

**Done:**
- [x] Every real Edge close: Jarvis + Tk popup (why + how to fix) + `data/logs/comms_incidents.jsonl`
- [x] Crash/quit watch: if `msedge.exe` disappears without a tracker kill, still log `edge_quit` + Jarvis/Tk (MessageBox fallback)
- [x] Tray: live ST/Gate ages, current why, last close, “View Edge-close / comms log”
- [x] Life Tracker + Android Comms: authentic ages, current issue, last Edge close
- [x] `GET /api/behavior/comms-incidents`

**Try:** Restart tracker · Reload extensions · tray Comms lines · close Edge only if both extensions really off · if Edge vanishes, expect a why/how window even when the tracker did not kill it

---

## 2026-08-18 — Tracker / extension / watch comms

**Done:**
- [x] `comms_health.py` — alive / stale / dead hysteresis; FP/FN reasons
- [x] Gate poll requires `X-CALT-Extension` (SPA cannot fake extension alive)
- [x] Skip new Edge window when extension is polling; close Edge only if dead + API up
- [x] Android + Life Tracker board show comms / why-rules-idle
- [x] Rebuild SelfTracker + CALT Gate service workers
- [x] `770` pytest · `npm run build`

**Try:** Reload both Edge extensions unpacked · Life Tracker comms strip · Android Comms card

---

## 2026-08-18 — Tracker API unified board

**Done:**
- [x] `build_productivity_snapshot()` — pulse, goals, focus quality, weekly snippet, study nudge
- [x] `GET /api/behavior/day-status` schema 3 (+ hub alias unchanged path)
- [x] `GET /api/behavior/export/activitywatch` (P2 export)
- [x] Android tracker pulse/goal/focus cards + recovery hint
- [x] Web `TrackerDayBoard` on Life Tracker (today)
- [x] `758+` pytest · `npm run build` green

**Try:** Life Tracker (tracker board) · CALT Android refresh · `GET /api/behavior/export/activitywatch?day=today`

---

## 2026-08-18 — Competitive productivity features (complete)

**Done:**
- [x] Productivity Pulse + GlanceBar goal %
- [x] Activities inbox + Goals/alerts (YouTube cap → study mode nudge)
- [x] Recovery capacity hint + Shutdown ritual + Away prompt
- [x] Overcommit check at plan confirm
- [x] Weekly digest, Focus quality badge, Recurring gate schedules
- [x] `757 passed` pytest · `npm run build` green

**Try:** Productivity → Calendar (digest, shutdown) · Plan (overcommit confirm) · Settings (schedules, activities).

---

## 2026-08-17 — Unattended unified quiz mandate

**Done:**
- [x] User chose shared quiz engine (option 1) + full autonomy while away
- [x] Design spec + implementation plan
- [x] AGENTS.md mandate refresh (retired stale cape-only Study Flow focus)
- [x] Cursor rules: `notes-generation.mdc`, `quiz-generation.mdc`
- [x] Vocab adaptive → ReviewCard bridge
- [x] StudyLoopWidget empty-state + Review Start CTAs
- [x] Weekly adherence empty state
- [x] Bible today-chapter assignment no longer skips from `assigned_key`
- [x] Day ribbon uses calendar overlay (sleep clips overnight PC time)
- [x] Focus Rhythm: Calendar day/week/month zone, pulled-away, and distraction-source story
- [x] Verify full pytest + build

**Try on return:** GRE Cycle quiz → open `/review` for vocab cards · Lecture Notes quiz · Math Start · Calendar empty states.

---

## 2026-08-15 — Manual health dumper (CALT Sync 4.0)

**Done:**
- [x] Watch: Dump/Send only, 7-day queue, health-only app-side; removed plans/calendar/notify/background
- [x] Backend: idempotent ingest events, field-aware merge, monotonic activity, no JSON truncate
- [x] Life Tracker + hub projections duplicate-safe (`client_event_id`)
- [x] Tests + `docs/CALT_SYNC_MANUAL_DUMP.md` + Productivity panel copy
- [x] Alembic `0028_wearable_ingest_replay`

**Try:** Sideload Sync 4.0.0 · Dump + Send · confirm one Life row per day · resend same chunk → duplicate ACK.

---

## 2026-08-05 — Edge-only browser catalog + Settings

**Done:**
- [x] `backend/behavior/browser_catalog.py` — allowed Edge; known browsers + installer soft-lock
- [x] Distraction gate / API payload / tracker soft-lock kind `browser_installer`
- [x] Voice + tray + Plan/Calendar copy: Edge only
- [x] Settings → Tracker setup: Edge SelfTracker load/reload steps

**Try:** Restart tracker + API · Reload Edge SelfTracker · open Chrome while STUDY → soft-lock.

---

## 2026-08-05 — Edge-only (drop Zen)

**Done:**
- [x] Removed `selftracker-extension-firefox/` + Zen install/launch scripts
- [x] `allowed_browsers` / `ALLOWED_BROWSER_EXES` → `msedge.exe` only
- [x] `open_url_preferred` → Edge; docs + policy panel updated
- [x] Kept historical “— Zen Browser” title parsers for old CSV logs

**Try:** Reload Edge SelfTracker 1.5.3 · restart desktop tracker + API. Study browsing = Edge only.

---

## 2026-08-05 — Tight gate UX (free-life + plan goals)

**Done:**
- [x] `FREE_LIFE` wired in `browser_gate_policy` (`allow_free_life`, `free_life_allow_domains`); errands-lite keeps YouTube blocked
- [x] Morning confirm requires goals (≥3); `plan_exists` → Add more vs Confirm as-is + Jarvis `plan_exists_ask`
- [x] Debounce / `open_or_focus_calt` tests; free allows amazon / study blocks amazon

**Try:** Reload Edge SelfTracker 1.5.3 · restart desktop tracker + API.

---

## 2026-08-05 — Zen/Firefox SelfTracker 1.5.3 (webRequest hard-block)

**Broken (installed XPI was 1.5.1):** missing `webRequest`/`webRequestBlocking`; no network hard-block; incomplete one-tab soft-land / FOCUS_CALT / Jarvis / calt-tab-command vs Chromium 1.5.3.

**Done (Firefox folder only):**
- [x] `webRequest` blocking → `locked.html` for watch + porn; soft-land one CALT tab
- [x] Manifest 1.5.3 + `windows` perm; no `importScripts` / no DNR
- [x] Keep one-tab sweep, FOCUS_CALT, poll calt-tab-command, JARVIS_LINE, FREE_LIFE (gate_policy)
- [x] Edge/Chromium `selftracker-extension/` left alone

**Try:** fully quit Zen → `scripts\install_selftracker_zen_permanent.bat` → reopen Zen → about:addons shows **1.5.3**.

---

## 2026-08-04 — Today’s rules panel on desktop tracker

**Done:**
- [x] Pure helpers `tracker_rules.py` — what’s next / checklist / Armed / hint / wake / extras from gate JSON
- [x] Tk window `tracker_rules_gui.py` — tray **Today’s rules**; polls gate ~15s while visible
- [x] Hard-block lock card embeds same “Today’s rules” section + Open Productivity
- [x] Tray status line + tooltip show morning next; tests `tests/test_tracker_rules.py`

**Try:** restart desktop tracker → tray → **Today’s rules** (or trigger a lock card).

---

## 2026-08-04 — Jarvis canned dialogues + morning brief

**Done:**
- [x] Expanded dialogue bank: `voice_agent/dialogues.py` (+ gate pools via `block_dialogues`) — morning greet/nudge/praise, plan, tasks, stats, yesterday plan hint, idle, goodbye
- [x] Once/day morning brief (`morning_brief.py`) — flag `data/voice_agent/morning_briefed_{date}.json`; tracker gate after 5am if bible/plan pending; chat open; `/brief` forces
- [x] Reactive speak: bible tick praise, plan confirm praise, gate blocks (existing)
- [x] LLM prompt: more reactive free chat; rituals are system-spoken separately
- [x] Tests: `tests/test_voice_dialogues.py` (+ existing voice/gate green)

**Try:** restart tracker (+ API if bible/plan hooks) → tray Voice chat `/brief` · mark Bible done · confirm plan → hear canned lines.

---

## 2026-08-04 — Keywords + light NSFW + Zen/Edge + canned voice (v1.3)

**Done:**
- [x] Keyword blocklist (URL/title only) in `browser_gate_policy` + SelfTracker v**1.3.0**
- [x] Optional CPU NSFW screen scan (`nsfw_screen_scan`) when Armed; ~60s; no GPU video
- [x] Unauthorized browsers (not Zen/Edge) → soft-lock + speak (never kill Cursor)
- [x] Canned Jarvis pools in `voice_agent/block_dialogues.py` — no LLM for routine blocks
- [x] Tests: `tests/test_gate_keywords_nsfw.py` (18 with browser_gate_policy)

**Try:** restart API + tracker → Reload Edge ext + re-load Zen add-on → Arm hard-block → YouTube/porn keyword → hear canned line; Chrome → unauthorized soft-lock.

---


## 2026-08-04 — SelfTracker browser gate policy (v1.2)

**Done:**
- [x] `backend/behavior/browser_gate_policy.py` — allowlist / porn / watch lists; nested `browser` on distraction-gate
- [x] Extensions (Chromium + Firefox/Zen) consume `browser` + morning soft-landing; version **1.2.0**
- [x] Tests: `tests/test_browser_gate_policy.py` (+ existing distraction_gate still green)
- [x] Docs: SETUP / DEPENDENCIES reload notes; future nude OCR deferred in hard-block spec addendum

**Try:** restart API → Reload Edge extension + re-load Zen temporary add-on → open Colab (allowed) / YouTube (blocked while Armed or morning locked).

---

**Done:**
- [x] `MORNING_GATE=1` set in `.env` (enforced: bible -> plan confirm -> open)
- [x] API + desktop tracker restarted to load today-only Bible + rewards + gate
- [x] Hard-block / Armed left unchanged

**Try:** login -> read today's chapter (web `/bible` or tracker) -> Confirm plan on Productivity -> unlock.

---
## 2026-08-04 — Bible today-only (one chapter / day)

**Done:**
- [x] `resolve_today_chapter` + `GET /api/bible/v2/today` — sequential plan, day-stable assignment, `plan_cursor` advance
- [x] Web `/bible`: hide book list / chapter grid; title + text + mark done; “Done for today” + verse preview
- [x] Tracker embed: hide chapter chips; tick today’s chapter only; lock card names today’s chapter
- [x] Tick rejects non-assigned chapters; morning gate / ≥1 chapter goal unchanged
- [x] Tests in `tests/test_bible_structured.py`

**Try:** restart API → open `/bible` (only today’s chapter). Tracker restart if using embed/lock card.

---

## 2026-08-04 — Morning unlock chain + rewards

**Done:**
- [x] Spec: `docs/superpowers/specs/2026-08-04-morning-unlock-rewards-design.md`
- [x] Unified bible-done: tracker `toggle_chapter_manual` / `mark_chapters_complete` now sync day `chapters_completed` (same as web tick)
- [x] Minimal rewards: `backend/planner/morning_rewards.py` — Bible +10, Plan +10 in `data/morning_rewards.json`
- [x] Gate payload: `morning.rewards` + `morning.hint`; UI copy on MorningGateRedirect / TodayPanel / Bible
- [x] Unit tests: `tests/test_morning_rewards.py` + gate/bible tick updates

**Try:** login → Bible tick (web or tracker) → Productivity Confirm. Disable: `MORNING_GATE=0`

---

## 2026-08-04 — Voice TTS modes (Jarvis filter + Normal)

**Done:**
- [x] `jarvis` (default) vs `normal` TTS modes — env `VOICE_AGENT_TTS_MODE`, file `data/voice_agent/tts_mode.json`, chat UI toggle, `/voice` command
- [x] Jarvis DSP post-filter (`jarvis_filter.py`) on WAV; Edge converts MP3→WAV best-effort; fail soft
- [x] Unit tests for mode persistence, filter, `/voice` parsing

**Try:** restart tracker → Voice agent → **Jarvis** / **Normal** buttons (or `/voice normal`)

---

## 2026-08-04 — Voice GPU session pipeline (phases 1–3)

**Done:**
- [x] Spec: `docs/superpowers/specs/2026-08-04-calt-voice-gpu-session-design.md` (session-based, **no wake word**, VRAM notes)
- [x] `SentenceStreamChunker` + session lifecycle (`chunker.py`, `session.py`)
- [x] Optional faster-whisper STT (try/import, session unload); edge-tts unchanged
- [x] Stream LLM → chunker → sentence TTS; Ollama `keep_alive=0`; fallback to full-reply speak
- [x] Tools + confirm gates unchanged; hotkey-only PTT

**Deferred:** Kokoro TTS, Windows power-cap `.bat`

**Try:** restart tracker → `Ctrl+Shift+Space` (or tray → Voice agent → Mic)

---

## 2026-08-04 — Voice agent action tools

**Done:**
- [x] Allowlisted tools in `backend/behavior/voice_agent/tools.py`: `web_search`, `open_url`, `open_app`, `play_music`, `media_play`, `volume_up`/`down`/`mute`, `set_volume`, `system_info`
- [x] Kept confirm-gated `pc_lock` / `pc_sleep` / `pc_shutdown` / hard-block; no arbitrary `run_command`
- [x] Unit tests for allowlist / URL scheme / search URL + prompt listing

**Try:** tray → Voice agent — “search for numpy broadcasting”, “open notepad”, “play lo-fi on Spotify”, “what’s my system status?”, “lock the PC” (confirm).

---

## 2026-08-04 — Voice agent Jarvis TTS

**Done:**
- [x] TTS stack: `edge-tts` (default `en-GB-RyanNeural`) → Piper → SAPI; env `VOICE_AGENT_TTS` / `VOICE_AGENT_VOICE`
- [x] Light butler/Jarvis personality in voice system prompt (concise, dry wit, "sir" sparingly)
- [x] Unit tests for TTS preference / fallback order (no network)

**Try:** `pip install edge-tts`, restart desktop tracker, tray → Voice agent (chat).

---

## 2026-08-04 — Remove Study Flow + corpus UI/API

**Done:**
- [x] Removed Topic Study Flow page, routes, nav, client, and `POST /api/transcripts/study-flow/start`
- [x] Removed Knowledge Base UI (`LibrarySetupPage` / `/knowledge-base`) and unmounted `/api/corpus` router
- [x] Replaced live `backend/corpus/` with thin stubs (`corpus_available()` → False) so Lecture Notes + app boot without RAG
- [x] Left `data/raw_library/` and quiz/SRS/GRE intact; skipped `export-bundle/`

**Next:** Use Lecture Notes for transcripts; Review Hub for due cards.

---

## 2026-07-26 — Calendar toolbar UX (full)

**Done:**
- [x] Custom `PlannerCalendarToolbar`: ‹ › Today · date chip + mini-cal popover · D|W|M icon toggles
- [x] `MiniCalendarPopover`: month grid; D/W/M synced pick; week single + multi-week range (snap Mon–Sun); Today / Clear range
- [x] Multi-week: RBC Week remains 7 days — navigate to range start, chip + mini-cal keep full span highlight

**Try:** Productivity → Calendar → click date chip; in W mode click a week then another to extend.

---

## 2026-07-26 — Calendar 2D hour rendering

**Done:**
- [x] Spec: `docs/superpowers/specs/2026-07-26-calendar-2d-hour-rendering-design.md`
- [x] Backend `hour_slices` on `GET /api/planner/overlay/actual` (`backend/planner/hour_slices.py` + tests)
- [x] Day-view 2D track layer (`DayGridActualLayer` / tiers / seam / sleep lane 0 / legend)
- [x] Toggle: Day view → **2D track** (hides RBC actuals; keeps plan)

**Deferred:** empty-hour compression, hour focus-modal, SVG polygon outlines.

---

## 2026-07-19 — Cape-time doc revamp + ship to main

**Done:**
- [x] Merged / pushed study-flow, quiz practice loop, productivity policy, wearables, propose-plan, easter eggs to `main` (`e3c5bd9`)
- [x] Fixed missing `AppErrorBoundary` import (frontend white-screen)
- [x] Revamped `AGENTS.md`, `COMPLETION_SPRINT.md`, `PROJECT_STATUS.md`, `TASK_COMPLETION.md` for wrap-up mode

**Next (Sprint 4):**
- [ ] One-lecture A5 acceptance (pick transcript; document name here)
- [ ] GRE Lane C smoke
- [ ] `python -m pytest tests/ -q`
- [ ] `npm run build`

**Blocked / notes:** Local DBs, APK, GRE PDFs stay untracked by design.

---

## 2026-07-07 — Blank screen fix (post read-time scores)

**Done:** `serialize_session` alias; regression tests for `/api/behavior/stats` CSV path + `/api/planner/overlay/actual`; `AppErrorBoundary` (reload UI instead of white screen on HMR crashes). **Recovery:** full restart `run.bat` + browser Ctrl+Shift+R after migration `0023`.

---

## 2026-07-07 — Productivity score read-time + effective focus

**Done:** `category_scores` table + `tracked_sessions_scored` view; scores derived from category at read time (dropped `tracked_sessions.productivity_score`). `PRODUCTIVE_THRESHOLD` raised **50 → 60** for `productive_minutes` and new `effective_focus_minutes` adherence KPI.

---

## 2026-06-25 — Second brain loop

**Done:**
- [x] Full PDF ingest (CLI, API, Knowledge Base UI, auto-setup)
- [x] Grounded notes button on Lecture Notes (`CORPUS_GROUNDED_NOTES=1`)
- [x] Studio Done → auto-ingest transcript + note into corpus
- [x] Web generate → corpus handoff after save
- [x] `build-golden` CLI + expected chunk counts in `CORPUS_STATUS.md`
- [x] Markdown code-block extraction + repair pipeline fixes

**Verify (still useful in Sprint 4):**
- [ ] `CORPUS_GROUNDED_NOTES=1` in `.env`, restart backend
- [ ] Knowledge Base → Build (or status shows ~3500+ chunks)
- [ ] Lecture Notes → Generate grounded (RAG) on a transcript
- [ ] `python -m pytest tests/test_corpus.py -m integration`

---

## Phase 1 — GRE Vocabulary ✅

See [GRE_VOCAB_PHASE1.md](GRE_VOCAB_PHASE1.md). ROADMAP marks Phase 1 complete.

---

## Session template

```markdown
## YYYY-MM-DD

**Today's task:** [one item]

**Done:**
-

**Blocked / notes:**
-
```

## 2026-07-03 — Plan vs Actual dashboard

Plan vs Actual dashboard on Productivity calendar tab — consumes `/api/planner/blocks`, `/overlay/actual`, `/adherence`, `/api/behavior/desktop-timeline`, `/tracker-health`.

## 2026-07-07 — Activity detail UX

Calendar tab layout (Today strip + full-width planner); day sync calendar↔ribbon; shared ActivityDetailPanel with click drill-down on Day ribbon and calendar stacks.

## 2026-07-07 — Read-time productivity scores

`category_scores` table + `tracked_sessions_scored` view; scores derived at read time from category. `productive_minutes` threshold raised 50→60 (matches `PRODUCTIVE_THRESHOLD`); added `effective_focus_minutes` adherence KPI.
