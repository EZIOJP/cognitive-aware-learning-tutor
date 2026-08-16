# Life Tracker — unify one day’s data (brief for Claude / Gemini)

**Date:** 2026-08-15  
**Product:** Cognitive-Aware Learning Tutor (local-first study dashboard)  
**Page:** Life Tracker (`/life` or equivalent route)  
**Ask:** Propose a single-feature layout that stops repeating the same day metrics across Watch dump, Life Score, Life Clock, and Health pillars. Return a concrete wireframe + component hierarchy. Do not invent new sensors or edit APIs unless necessary.

---

## Problem

On Life Tracker, **the same day** is shown in several panels that feel like separate products:


| Current block                           | What it shows                                                                                    | Data source                            |
| --------------------------------------- | ------------------------------------------------------------------------------------------------ | -------------------------------------- |
| Banner “Watch-connected day”            | Sync status copy                                                                                 | cosmetic                               |
| **Watch Insights** (`WatchDayDumpCard`) | Sleep score, duration, window, hypnogram, stages, steps, kcal, distance, HR/stress/stand/battery | `GET` wearables day + `payload`        |
| **Life Clock** (`LifeClockWidget`)      | Time-balance / day ring (also pulls hub/life daily internally)                                   | hub / life daily for selected day      |
| **Life Score** + pillar rings           | Composite 0–100 + Health / Productivity / Digital / Mental                                       | `computeScores(entry)` from life daily |
| **14-day Life Score trend**             | Bars of past life scores                                                                         | 14× `fetchLifeDaily`                   |
| **Daily pillars** (accordion)           | Sleep hours/quality, exercise, water… (sourced vs empty)                                         | same `entry` as Life Score             |


**User complaint:** Sleep / Move / Watch dump / Life Tracker are not different features — they are **one day’s wellbeing**. Separate “Sleep” vs “Move” headers and separate Watch vs Score vs Health sleep rows feel redundant.

**Goal:** Redesign Life Tracker as **one Day feature** with clear hierarchy: one hero, one detail surface, one score/explain surface — not four dashboards stacked.

---



## Constraints (do not ignore)

1. **Read-only page** — no habit logging inputs; copy must not imply editable fields.
2. **Two APIs stay** (wiring, not UX):
  - Life / hub daily → scores + clock + pillars  
  - Wearables day dump → rich sleep stages + move + vitals  
   Scores and watch payload can **disagree**; layout ≠ merge math unless specified.
3. `WatchDayDumpCard` **is shared** with Productivity → Wearables sync panel. Visual changes leak there; prefer props (`variant="compact" | "full"`) or extract presentational pieces.
4. **Cape-time product rule:** presentation / information architecture only — do not expand wearables ingest, life-clock skins, or new pillars unless asked.
5. **Empty honesty:** hide zeros / unsourced (`source="—"`) rows; don’t show fake mood/water as real.
6. **Design system:** dark glossy panels (`gloss-panel`), existing Tailwind tokens — avoid generic purple-on-white AI template look.

---



## Overlap map (same facts, multiple places)

```
Sleep hours / quality     → Watch Insights + Health pillar + (sometimes) Life Clock context
Steps / move              → Watch Insights only (Life Score may use exerciseMinutes estimate)
Composite “how am I?”     → Life Score rings + pillar accordions (breakdown of same scores)
“What did my day look like?” → Life Clock (time categories) vs Watch (biometrics)
```

**Principle for redesign:** each fact appears **once** at the strongest level; other places link or disappear.


| Fact                          | Show once as                                                            | Demote / remove                                        |
| ----------------------------- | ----------------------------------------------------------------------- | ------------------------------------------------------ |
| Sleep stages + score + window | Watch detail (hero or primary chart)                                    | Health pillar sleep rows (or replace with “see Watch”) |
| Steps / kcal / distance       | Same hero metric strip as sleep                                         | Separate “Move” section (already collapsing)           |
| HR / stress / stand / battery | Compact vitals row under hero                                           | Nowhere else                                           |
| Life Score 0–100 + 4 pillars  | Score summary (right rail or sticky)                                    | Don’t restate sleep numbers inside score card          |
| Pillar input rows             | Only **sourced** non-biometric inputs (pomodoro, etc.)                  | Duplicate watch sleep                                  |
| Life Clock                    | “Time use” facet of the day (apps/categories), not a second health dump | Don’t put sleep rings here                             |
| 14-day trend                  | Collapsed under score or secondary                                      | Not competing with today’s hero                        |


---



## Suggested information architecture (recommended)

Treat the page as **one feature: Day**.

```
┌─ Day chrome ─────────────────────────────────────────┐
│ Title · day prev/next · Refresh                      │
│ One status line (synced / missing watch)             │
└──────────────────────────────────────────────────────┘
┌─ A. TODAY HERO (watch + score fused) ────────────────┐
│  Big: Life Score OR Sleep score (pick one primary)   │
│  Strip: asleep · steps · kcal · distance · vitals    │
│  Chart: hypnogram (if stages)                        │
│  Chips: deep/light/rem/wake + step %                 │
└──────────────────────────────────────────────────────┘
┌─ B. DAY IN TIME (Life Clock) ──┬─ C. SCORE BREAKDOWN ┐
│  Time balance / categories     │  4 pillar rings     │
│  (focus / distraction / etc.)  │  14-day trend       │
└────────────────────────────────┴─────────────────────┘
┌─ D. SOURCES (optional, collapsed) ───────────────────┐
│  Accordion: only non-duplicated pillar inputs        │
│  “Show raw watch payload”                            │
└──────────────────────────────────────────────────────┘
```



### Primary number (choose one — recommend for Claude)

- **Option P1 — Life Score primary:** Hero number = composite; watch metrics are the evidence strip. Best if the page’s job is “am I balanced?”
- **Option P2 — Watch recovery primary:** Hero = sleep score + duration; Life Score sits in the side rail. Best if the page’s job is “what did the watch say?”
- **Recommendation:** **P1** for Life Tracker route; keep full watch dump richness in the same hero so users don’t scroll past score to find sleep.

---



## Three layout approaches (ask model to pick + wireframe)



### Approach A — “Single Day card” (recommended)

One large card owns watch metrics + hypnogram + vitals. Life Score is a **module inside that card** (left chart / right score) or a tight sibling in the same row. Pillars become a **footer drawer**, not a second page of stats. Life Clock is the only other full-width block (“how time was spent”).

**Pros:** Matches user mental model (“one day”).  
**Cons:** Big card; need careful density on mobile.

### Approach B — “Tabs inside Day”

Tabs: **Body** (watch) · **Time** (clock) · **Score** (rings + trend + sourced inputs). Same shell, day nav shared.

**Pros:** No scroll war; clear facets.  
**Cons:** Hides score or sleep behind a click; worse for at-a-glance.

### Approach C — “Score-first dashboard”

Life Score + trend first; Watch Insights collapsed to “Sensors” expandable; Clock secondary.

**Pros:** Emphasizes product’s life-score story.  
**Cons:** User already said watch + tracker feel like the same space — burying watch may feel wrong.

---



## Files involved (implementation later)


| Path                                       | Role                                                  |
| ------------------------------------------ | ----------------------------------------------------- |
| `src/pages/LifeTrackerPage.tsx`            | Page shell, day nav, score, pillars, section order    |
| `src/components/life/WatchDayDumpCard.tsx` | Watch payload visualization (shared)                  |
| `src/components/hub/LifeClockWidget.tsx`   | Embedded time-balance (also used elsewhere — careful) |
| `src/styles/life-tracker.css`              | Page-specific surfaces                                |
| `src/api/wearablesClient.ts`               | Wearable day fetch                                    |
| `src/api/hubClient.ts`                     | `fetchLifeDaily`                                      |
| `src/context/GoalTrackerContext.tsx`       | `computeScores`, `DailyEntry`                         |


**Out of scope for this redesign:** new wearables sync flows, editing habits, Figma-only polish without IA change.

---



## What to ask Claude / Gemini

Paste this whole file and ask:

1. Critique Approach A/B/C for a **round-watch-synced, read-only** day page.
2. Produce a **mobile + desktop wireframe** (ASCII or markdown) for the recommended approach.
3. Define a **component tree** (`DayHero`, `DayTimeBalance`, `DayScoreRail`, …) mapping to the files above.
4. Specify **what to delete or hide** (exact duplicate rows) so sleep never appears three times.
5. Call out **one primary number** (Life Score vs Sleep score) and why.
6. Keep **Amazfit dump fields** (stages, naps, targets) visible without a second “Move” section.
7. Do **not** propose new backend fields in v1.

---



## Acceptance criteria (for later implementation)

- [ ] User can answer “How was today?” without scrolling past three redundant sleep UIs.  
- [ ] Watch stages + move + vitals still visible when payload exists.  
- [ ] Life Score + pillar breakdown still visible.  
- [ ] Life Clock still visible as time-use, not a second health card.  
- [ ] Unsourced pillar rows stay hidden.  
- [ ] Wearables sync panel still works if card gains a `variant` prop.  
- [ ] No new feature lane beyond layout / IA.

---



## Current page order (as of 2026-08-15)

1. Header + day nav
2. Watch-connected banner
3. Watch Insights (combined metric strip + hypnogram — Sleep/Move headers removed)
4. Life Clock | Life Score + 14-day trend
5. Daily pillars accordion

**Desired direction:** collapse 2–5 into the **Day** IA above so Watch dump and Life Tracker are one feature, not stacked mini-apps.