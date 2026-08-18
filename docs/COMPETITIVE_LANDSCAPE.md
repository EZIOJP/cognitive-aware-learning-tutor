# Competitive landscape — productivity, focus, and health

Last updated: 2026-08-18

Purpose: scout total competition, note what to borrow, and track CALT weak points. Companion to RescueTime borrow list from same session.

**CALT positioning:** local-first **study + productivity OS** — plan vs actual, distraction gate, wearables on one day ribbon, GRE/math/notes loop. Not a SaaS time tracker.

---

## Market map (who we compete with)

```text
                    PLANNING / CALENDAR              TRACKING / SCORES
                    ─────────────────              ─────────────────
Intentional daily   Sunsama · Akiflow · Motion      (Sunsama: estimate vs actual)
AI auto-schedule    Motion · Reclaim · Akiflow      Reclaim: defend focus blocks
Passive tracking    —                               RescueTime · Rize · ActivityWatch
Blocking            Freedom · Opal                   RescueTime Focus · Rize blocker
Health readiness    —                               Whoop · Oura (recovery → capacity)
Open / local        —                               ActivityWatch · Gadgetbridge
Study-specific      —                               CALT (unique lane)
```

---

## Master comparison

| Product | Core job | Strongest features | Price signal | CALT overlap |
|---------|----------|-------------------|--------------|--------------|
| **RescueTime** | Where did time go? | Productivity Pulse, goals/alerts, Activities inbox, Focus Session | ~$12/mo | High — tracking + block |
| **Rize** | AI time + focus quality | Auto sessions, Focus Quality Score, context-switch alerts, calendar merge | ~$10–20/mo | High — coach layer |
| **Sunsama** | Calm daily plan | Guided planning + shutdown, workload warning, estimate vs actual | ~$20/mo | Medium — ritual + capacity |
| **Motion** | AI schedules your week | Auto-scheduling, deps, chunking, re-plan on change | ~$19/mo | Medium — planner only |
| **Reclaim.ai** | Defend focus on calendar | Focus Time goals, proactive/reactive, habits, auto-reschedule | Freemium+ | Medium — calendar defense |
| **Akiflow** | Inbox zero → calendar | 3000+ integrations, keyboard triage, meeting action items | ~$15/mo | Low — integrations |
| **Freedom** | Block everywhere | Cross-device sync, recurring schedules, Locked Mode, allow-only | ~$40/yr | Medium — block only |
| **ActivityWatch** | Local passive track | Open source, watchers, categories, REST API, privacy | Free | Medium — capture only |
| **Whoop** | Body readiness | Recovery score, strain target, sleep need, daily coach | Hardware+sub | Medium — wearables half |
| **CALT** | Study day + truth | Plan vs actual, gate, wearables ribbon, local, quiz loop | Personal | — |

---

## Deep dives — what they do well

### 1. RescueTime (tracking + coach + block)

**How it works:** Desktop agent → active window (app + URL + title, no keystrokes) → cloud sync → 5 productivity levels → **Productivity Pulse** (0–100) → goals (all-day progress) + **alerts** (instant threshold) → optional Focus Session block.

**Steal:**
- Single daily **Pulse** score with published weights
- **Goals vs alerts** (progress bar vs one-shot nudge)
- **Activities** page: ranked apps/sites, bulk edit, **Sort uncategorized** inbox
- Alert → auto Focus Session
- Away-from-desk prompt on return
- Work-hours logging schedule + ignore forever
- Weekly email digest

**Weak vs CALT:** No planner adherence, no wearables, no study loop, cloud-only.

---

### 2. Rize (AI tracking + focus quality)

**How it works:** Mac/Windows agent → AI tags client/project from titles/URLs/calendar → auto **Focus / Meeting / Break** sessions → **Focus Quality Score** (20+ signals, context switches) → distraction blocker on pattern → review panel on calendar.

**Steal:**
- **Auto session detection** (focus vs meeting vs break) without manual timer
- **Focus quality** during blocks (switches inside “study” session)
- **Pending entries** review docked to day timeline
- Plain-English “why this tag” for classifications
- Calendar-aware meeting sessions

**Weak vs CALT:** No plan vs actual, no hard gate, no local-first, team/billing oriented.

---

### 3. Sunsama (planning ritual + capacity)

**How it works:** Mandatory **daily planning** (5 Ps) + **shutdown** → pull tasks from integrations → **estimate duration** → compare total planned time vs **workload threshold** → timebox on calendar → track **actual vs estimate** over weeks.

**Steal:**
- **Guided shutdown** (review done, carry forward, mental closure)
- **Overcommit warning** before day starts (planned minutes vs capacity)
- **Estimate accuracy loop** (planned vs actual per task type)
- Scheduled ritual prompts (Settings → plan at 8am)
- “Defer / backlog” when over capacity (`D` / `Z` pattern)

**Weak vs CALT:** Weak blocking, no desktop exe kill, no wearables, expensive, cloud.

---

### 4. Motion (AI auto-schedule)

**How it works:** Tasks with duration, deadline, priority, deps → AI places on calendar → **re-optimizes** when meetings land → chunking long tasks → work hours + buffers.

**Steal:**
- **Roll-forward** when day slips (auto reschedule remaining blocks)
- **Chunking** (6h project → 3×2h)
- **Dependency** between tasks
- One-click “rebuild today” after disruption

**Weak vs CALT:** No actual tracking proof, no gate, no health; feature bloat complaints.

---

### 5. Reclaim.ai (defend focus time)

**How it works:** Sits on Google/Outlook → **Focus Time weekly goal** → proactive (fill early) or reactive (defend when full) → blocks **move** when higher-priority meeting added → Habits + Tasks count toward focus goal.

**Steal:**
- **Weekly focus hour goal** with calendar **defense**
- Proactive vs reactive scheduling modes
- **Flexible blocks** that reschedule instead of breaking
- Focus goal progress visible on calendar

**Weak vs CALT:** Calendar-only; doesn’t know if you actually worked in the block.

---

### 6. Akiflow (triage + integrations)

**How it works:** Universal inbox from 3000 tools → keyboard-first plan/snooze → drag to calendar → conflict detection → meeting action items → Schedule Optimizer (2025).

**Steal:**
- **Command bar** natural language capture
- **Inbox zero** workflow with bulk actions
- **Conflict detection** on calendar
- Meeting → task extraction

**Weak vs CALT:** No automatic desktop proof, weak mobile, no health.

---

### 7. Freedom (blocking)

**How it works:** Blocklists across Mac/Win/iOS/Android/Chrome → **recurring schedules** → **Locked Mode** (can’t end early) → allow-only sessions → multi-device sync.

**Steal:**
- **Recurring block schedules** (weekday 9–12 study)
- **Locked Mode** (commitment device — align with gate “no override”)
- **Allow-only** mode (whitelist for research)
- Cross-device session sync (extension + desktop + phone)

**Weak vs CALT:** No tracking, no plan, no scoring.

---

### 8. ActivityWatch (open local tracker)

**How it works:** Watchers (window, AFK, browser, editor) → local SQLite → categories via rules → REST API → optional sync (WIP).

**Steal:**
- **AFK watcher** separate from active window (clean idle)
- **Category rules** as regex + canonical query pipeline
- **REST API** for all buckets (we have internal API; could document)
- **Pause logging** + export canonical events
- Watcher plugin architecture

**Weak vs CALT:** No coach, no plan, no block, no wearables UI.

---

### 9. Whoop (recovery → daily capacity)

**How it works:** 24/7 physiology → morning **Recovery %** → **Strain target** for day → sleep need adjusted by debt + strain → coach nudges.

**Steal:**
- **One morning readiness number** (we have sleep score + watch data — unify)
- **Recommended effort band** for the day (map recovery → planner/gate softness)
- “Green/yellow/red” plain language
- Strain accumulates through day vs target

**Weak vs CALT:** No desktop productivity, subscription hardware.

---

## CALT strengths (keep — do not trade away)

| Strength | Why it matters |
|----------|----------------|
| **Plan vs actual adherence** | RescueTime/Rize don’t natively score “on-plan focus” |
| **Day ribbon** (plan + actual + sleep clip) | Single visual day — rare in market |
| **Distraction gate + desktop hard-kill** | Stronger than RescueTime Focus for gaming |
| **Morning flow** (bible → plan confirm → study mode) | Sunsama-like ritual but enforced |
| **Wearables on same day** | Whoop metrics + productivity overlay |
| **Local-first / no cloud lock-in** | ActivityWatch privacy + full app |
| **Study loop** (notes → quiz → SRS) | None of the above competitors |
| **LLM classification review** | Rize-like but local Ollama path |

---

## CALT weak points (honest gaps)

### Capture & classification
- [ ] No single **Productivity Pulse** (0–100) — scores exist but no canonical daily number
- [ ] No **per-category / per-app goals + real-time alerts** (only daily productive gate goal)
- [ ] **Activities manager** weak — ClassificationReview exists; no ranked “top apps this week” + bulk edit UX
- [ ] **Uncategorized inbox** not prominent (RescueTime “Sort uncategorized”)
- [ ] **Away/offline prompts** — idle gaps invisible
- [ ] **Logging schedule** (work hours only) — tracks 24/7
- [ ] macOS / Linux agent — Windows + extension only
- [ ] No **auto session types** (focus vs meeting vs break) like Rize

### Planning & rituals
- [ ] **Shutdown ritual** missing (Sunsama end-of-day)
- [ ] **Overcommit warning** — planned minutes vs capacity not surfaced at plan time
- [ ] **Estimate vs actual** per task type — blocks have duration but weak feedback loop
- [ ] **Auto reschedule** when day slips (Motion/Reclaim)
- [ ] **Weekly focus defense** on calendar (Reclaim proactive mode)

### Blocking & focus
- [ ] No **recurring block schedules** UI (Freedom-style weekdays)
- [ ] No **Locked Mode** (cannot disable gate mid-session without PIN)
- [ ] Alert → block not wired (threshold → study mode)
- [ ] Cross-device block sync limited (desktop + browser; no phone block list)

### Coach & reports
- [ ] No **weekly narrative digest** (email or in-app)
- [ ] No **context-switch score** inside focus blocks (Rize)
- [ ] Voice agent exists but not unified **Assistant** with live goal bar (RescueTime)
- [ ] Long-range trends (months) thin vs week/month heatmap

### Platform & integrations
- [ ] No **Health Connect import** (Android multi-brand wearables)
- [ ] Integrations: GCal only — no Slack/Notion/Linear inbox (Akiflow)
- [ ] No team/multi-user
- [ ] No mobile **usage** tracker (Android app is gate/status only)

### Health × productivity bridge
- [ ] Sleep/recovery not translated to **“recommended focus hours today”** (Whoop-style)
- [ ] Sitting/steps on ribbon but not tied to **nudges** (“stand 10m”)

---

## Borrow list — prioritized backlog

### P0 — High impact, fits CALT architecture
1. **Productivity Pulse** + display on GlanceBar / Productivity header
2. **Goals + Alerts** engine (category/app limits, tray toast, optional study mode)
3. **Activities + uncategorized inbox** UI (reuse `stats_aggregate`, `ClassificationReview`)
4. **Shutdown ritual** panel (carry tasks, review adherence, plan tomorrow stub)
5. **Recovery → daily capacity hint** from watch sleep/HRV (`suggested_focus_hours`)

### P1 — Strong differentiators when combined with plan
6. **Overcommit check** at morning plan confirm (planned min vs `daily_goal_minutes`)
7. **Away prompt** on idle return (`tracker_idle.py`)
8. **Weekly digest** component (pulse, adherence streak, top 3 drains)
9. **Recurring gate schedules** (Freedom-style) in policy panel
10. **Focus quality** metric — context switches during on-plan blocks

### P2 — Larger lifts
11. **Health Connect** reader (Android hub path)
12. **Auto roll-forward** planner blocks (Motion-lite)
13. **Reclaim-style focus defense** — tentative “deep work” blocks that move
14. **Rize-like session auto-detection** (focus/meeting/break)
15. **ActivityWatch-compatible export** API for power users

### P3 — Out of scope unless product pivot
- Akiflow-scale integrations (3000 tools)
- Team dashboards / billing (Rize team)
- Cloud SaaS multi-device sync
- macOS agent

---

## Feature theft matrix (quick reference)

| Feature | Best source | CALT file touchpoints |
|---------|-------------|------------------------|
| Daily pulse 0–100 | RescueTime | `stats_aggregate.py`, `GlanceBar.tsx` |
| Real-time alerts | RescueTime | new `goals_alerts.py`, `tracker_tray.py` |
| Uncategorized inbox | RescueTime | `ClassificationReview.tsx`, classification API |
| Focus quality / switches | Rize | `tracker_service.py`, `FocusRhythmPanel.tsx` |
| Shutdown ritual | Sunsama | `MorningAutoPlanPanel.tsx`, new shutdown component |
| Overcommit warning | Sunsama | `PlanningDayAgenda.tsx`, `day_metrics.py` |
| Auto reschedule blocks | Motion/Reclaim | `planner/service.py`, `auto_plan.py` |
| Recurring blocks | Freedom | `browser_gate_policy.py`, policy UI |
| Locked mode | Freedom | `distraction_gate.py`, gate extension |
| AFK + rules | ActivityWatch | `tracker_idle.py`, category rules |
| Recovery → capacity | Whoop | `wearables` + `hub/rollup.py`, morning brief |
| Local API | ActivityWatch | document `/api/behavior/*` OpenAPI |

---

## Strategic takeaway

**Do not become RescueTime.** Become the tool that answers:

> “Given how I slept and what I planned, did I actually do the right work — and what nudge do I need *now*?”

Copy **coach mechanics** (pulse, alerts, inbox, shutdown, recovery hint). Keep **plan vs actual + gate + wearables + study** as the moat none of them combine.

---

## Session notes (2026-08-18)

From RescueTime analysis thread — already agreed borrow items:
- Productivity Pulse formula
- 3 default alerts (YouTube cap, social cap, productive goal bar)
- Activities + uncategorized inbox
- Away prompt on idle
- Alert → study mode trigger

Universal sync thread (separate): per-OS native adapters → one CALT collection; not one BLE protocol.
