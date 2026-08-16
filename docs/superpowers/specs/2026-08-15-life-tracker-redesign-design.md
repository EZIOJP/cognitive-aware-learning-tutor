# Life Tracker Redesign

**Date:** 2026-08-15  
**Scope:** Presentation and information architecture only. No new APIs, pillars, or score/merge-math changes.  
**Source:** [Life Tracker unification brief](../../LIFE_TRACKER_UNIFIED_DAY_BRIEF.md)

## Decision

Use **Approach A — Single Day card**.

- Reject tabs: a read-only glance page should not make users click between health, time, and score facets.
- Reject score-first with collapsed sensors: the watch is part of the same daily story and must remain visible.
- Primary number: **Life Score**. Watch measurements form evidence beneath it, rather than a separate hero.

When no watch sync exists for the selected day, show only the Life Score within the hero. Do not render empty vitals, an empty hypnogram, placeholder chips, or zero values. Day chrome states plainly: “No watch data for this day.”

## Component tree and file mapping

```text
DayPage                                      src/pages/LifeTrackerPage.tsx
├─ DayChrome                                 new; inline or extracted
│  └─ title · day navigation · refresh · one status line
├─ DayHero                                   new
│  ├─ ScorePrimary                           Life Score and delta vs. yesterday
│  ├─ VitalsStrip                            asleep · steps · kcal · distance · vitals
│  ├─ HypnogramChart                         only if sleep stages exist
│  └─ StageChips                             sleep stages + step-goal percent
├─ DayBody                                   desktop two columns; mobile stack
│  ├─ DayTimeBalance                         wraps LifeClockWidget unchanged
│  └─ DayScoreRail                           pillar rings + collapsible 14-day trend
└─ DaySources                                sourced, non-duplicated inputs + raw dump
```

`WatchDayDumpCard.tsx` changes:

- Add `embedded?: boolean`, defaulting to `false`.
- When embedded, suppress its outer card chrome so it can live inside `DayHero`.
- Extract presentational `VitalsStrip`, `HypnogramChart`, and `StageChips` pieces from the existing component for reuse.
- Do not add another variant value and do not modify Productivity’s existing compact/full call sites.

`LifeClockWidget.tsx` remains behaviorally unchanged. Add this comment where it is mounted:

```ts
// TODO: LifeClockWidget re-fetches hub/life daily independently of
// LifeTrackerPage — candidate for prop-drilling in a later pass.
```

## Remove or hide duplicates

| Current item | Required action |
|---|---|
| Standalone “Watch-connected day” banner | Delete; fold status into DayChrome |
| Health pillar sleep hours/quality | Delete; sleep is shown only in DayHero |
| Health pillar exercise/move | Hide when it duplicates watch steps; retain only truly distinct sourced workout minutes |
| Standalone “Move” heading | Delete; sleep and movement share `VitalsStrip` |
| Sleep data in Life Clock | Audit and ensure absent; Life Clock is time categories only |
| Raw sleep restatements in Health pillar/score tooltips | Delete; rings show only pillar score |
| 14-day trend | Place inside DayScoreRail, collapsed by default |

## Wireframe

### Desktop

```text
┌────────────────────────────────────────────────────────────────────┐
│ ← Aug 15, 2026 →                              [Refresh]   synced    │
└────────────────────────────────────────────────────────────────────┘
┌────────────────────────────────────────────────────────────────────┐
│ DAY HERO                                                           │
│ ┌───────────────┐  asleep 7h32m · steps 8,412 · 412kcal · 5.8km   │
│ │  Life Score   │  HR 58 avg · stress low · stand 9h · batt 62%   │
│ │      82       │  ┌──────────────────────────────────────────┐  │
│ │ ▲ +4 vs y'day │  │       hypnogram (deep/light/rem/wake)    │  │
│ └───────────────┘  └──────────────────────────────────────────┘  │
│                       deep 18% · light 54% · rem 21% · wake 7%    │
└────────────────────────────────────────────────────────────────────┘
┌───────────────────────────────┬──────────────────────────────────┐
│ DAY IN TIME (Life Clock)      │ SCORE BREAKDOWN                  │
│ focus 3h10m · distraction 40m│ ○Health 88 · ○Productivity 74    │
│ [time-balance ring/timeline] │ ○Digital 65 · ○Mental 79         │
│                               │ ▸ 14-day trend                  │
└───────────────────────────────┴──────────────────────────────────┘
┌────────────────────────────────────────────────────────────────────┐
│ ▸ Sources (sourced inputs only · show raw watch payload)           │
└────────────────────────────────────────────────────────────────────┘
```

### Mobile

```text
┌──────────────────────────┐
│ ← Aug 15, 2026 →     ⟳   │
│ synced                   │
├──────────────────────────┤
│ Life Score               │
│     82   ▲ +4            │
├──────────────────────────┤
│ asleep 7h32m · steps 8412│
│ 412kcal · 5.8km          │
│ [hypnogram]              │
│ deep18 · light54 · rem21 │
├──────────────────────────┤
│ ▸ Vitals                 │
├──────────────────────────┤
│ Day in time              │
├──────────────────────────┤
│ Score breakdown          │
│ ▸ 14-day trend           │
├──────────────────────────┤
│ ▸ Sources                │
└──────────────────────────┘
```

## Out of scope

- New wearable sync flows or endpoints
- New pillars, inputs, or `computeScores` changes
- Refactoring the internal LifeClock fetch
- New Tailwind tokens or color system
- Editable fields
- Productivity WatchDayDumpCard call sites

## Implementation sequence

1. Add the non-breaking `embedded` prop to `WatchDayDumpCard`.
2. Extract reusable VitalsStrip, HypnogramChart, and StageChips presentational pieces.
3. Build DayHero in `LifeTrackerPage.tsx` using those pieces and ScorePrimary.
4. Build DayChrome and remove the standalone watch banner.
5. Wrap LifeClock in DayTimeBalance without another Day heading.
6. Build DayScoreRail with pillar rings and a collapsed 14-day trend.
7. Rebuild the pillar accordion into DaySources and remove duplicates listed above.
8. Update `life-tracker.css` for `.day-hero`, `.day-body-grid`, and `.day-sources`; remove obsolete stacked-section rules.
9. Manually verify both a synced-watch day and a no-watch-data day.

## Acceptance criteria

- “How was today?” is answerable without encountering three redundant sleep views.
- Watch stages, movement, and vitals remain visible when available.
- Life Score and pillar breakdown remain visible.
- Life Clock presents time use, not health data.
- Unsourced rows remain hidden.
- Productivity’s Wearables Sync panel is unaffected.
- No-watch days contain score only in the hero—no empty data UI.
- Work stays within presentation and information architecture.
