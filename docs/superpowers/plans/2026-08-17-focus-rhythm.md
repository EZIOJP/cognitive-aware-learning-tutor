# Focus Rhythm Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a clear day/week/month Focus Rhythm story to the Productivity Calendar.

**Architecture:** Derive focus classifications from the existing planner blocks and actual-overlay sessions in a pure productivity utility. A focused React panel consumes those results and follows the calendar range already supplied by `PlanVsActualDashboard`; no backend or persistence changes are required.

**Tech Stack:** React 18, TypeScript, Recharts, Tailwind, existing planner client/hooks.

## Global Constraints

- Reuse the Calendar's selected day and Day / Week / Month view; do not add a second range selector.
- “In the zone” means productive time overlapping a planned block; “Pulled away” means low-score time overlapping a planned block; “Focused elsewhere” means productive time outside a planned block.
- Ignore sleep sessions and malformed timestamps.
- No backend endpoints, new routes, or gate / wearable scope expansion.
- Do not commit unless explicitly requested.

---

### Task 1: Derive range-level focus rhythm data

**Files:**
- Modify: `src/components/productivity/planVsActualUtils.ts`

**Interfaces:**
- Produces `buildFocusRhythm(blocks, sessions, from, to, view, threshold?)`.
- Returns totals, local time buckets, top low-score sources, and strongest zone/pulled-away buckets.

- [ ] **Step 1: Add focused types and a pure range classifier**

```ts
export type FocusRhythmView = "day" | "week" | "month";

export type FocusRhythmBucket = {
  key: string;
  label: string;
  zoneMinutes: number;
  pulledAwayMinutes: number;
  focusedElsewhereMinutes: number;
};

export type FocusRhythm = {
  buckets: FocusRhythmBucket[];
  totals: Pick<FocusRhythmBucket, "zoneMinutes" | "pulledAwayMinutes" | "focusedElsewhereMinutes">;
  topDistractions: Array<{ name: string; minutes: number }>;
  strongestZone: FocusRhythmBucket | null;
  strongestPulledAway: FocusRhythmBucket | null;
};
```

Split session time at overlapping plan boundaries and bucket the classified duration by local hour, weekday, or calendar date.

- [ ] **Step 2: Verify TypeScript**

Run: `npm run build`

Expected: production build succeeds.

### Task 2: Render the Focus Rhythm panel

**Files:**
- Create: `src/components/productivity/FocusRhythmPanel.tsx`

**Interfaces:**
- Consumes `PlannerBlock[]`, `ActualSession[]`, `from`, `to`, and `FocusRhythmView`.
- Uses `buildFocusRhythm` from `planVsActualUtils`.

- [ ] **Step 1: Render the narrative and balance**

Show:

```tsx
<h3>Focus rhythm</h3>
<p>Most in the zone: Tue 9–10am · Most pulled away: Fri 7–8pm</p>
```

Use three labelled totals and a single segmented bar for in-the-zone, pulled-away, and focused-elsewhere time.

- [ ] **Step 2: Render responsive pattern chart and sources**

Use a stacked Recharts bar chart:

```tsx
<BarChart data={rhythm.buckets}>
  <Bar dataKey="zoneMinutes" stackId="rhythm" fill="#34d399" />
  <Bar dataKey="pulledAwayMinutes" stackId="rhythm" fill="#fb7185" />
</BarChart>
```

List up to three low-score app/site names, or state that no clear pull-away source was recorded.

- [ ] **Step 3: Add loading and sparse-data states**

Render a compact skeleton while planner data is loading. When all three totals are zero, explain: “Add planned blocks and keep the tracker running to see your focus rhythm.”

- [ ] **Step 4: Verify TypeScript**

Run: `npm run build`

Expected: production build succeeds.

### Task 3: Wire focus rhythm to Calendar view

**Files:**
- Modify: `src/components/productivity/PlanVsActualDashboard.tsx`
- Modify: `src/pages/ProductivityPage.tsx`

**Interfaces:**
- `PlanVsActualDashboard` receives `analyticsFrom`, `analyticsTo`, and `analyticsView`.
- `ProductivityPage` passes `statsRange.from`, `statsRange.to`, and the Calendar's `day` / `week` / `month` view.

- [ ] **Step 1: Pass the current Calendar range**

Keep `DayRibbon` bound to its selected day. Feed Focus Rhythm the parent range so it reflects the Calendar's Day / Week / Month control.

- [ ] **Step 2: Load the shared planner data once**

The dashboard uses existing `usePlannerBlocks` and `useActualOverlay` for the active analytics range and passes loading/data into `FocusRhythmPanel`.

- [ ] **Step 3: Verify production build**

Run: `npm run build`

Expected: production build succeeds without TypeScript or Vite errors.

### Task 4: Verify productivity regressions

**Files:**
- Verify: `tests/test_productivity_week_export.py`

- [ ] **Step 1: Run backend productivity tests**

Run: `python -m pytest tests/test_productivity_week_export.py tests/test_day_metrics.py -q`

Expected: all selected tests pass.

- [ ] **Step 2: Check editor diagnostics**

Run: inspect `FocusRhythmPanel.tsx`, `PlanVsActualDashboard.tsx`, `ProductivityPage.tsx`, and `planVsActualUtils.ts` for new lints.

- [ ] **Step 3: Record verification**

Update `docs/SESSION_LOG.md` with the Focus Rhythm feature and the exact build/test results.
