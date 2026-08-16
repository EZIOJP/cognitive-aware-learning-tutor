# CALT Productivity Calendar — 2D Hour Rendering

**Date:** 2026-07-26  
**Status:** Approved (tightened) — implement per build order below  
**Related:** [2026-07-26-calendar-hour-peek-safe-design.md](./2026-07-26-calendar-hour-peek-safe-design.md) (safe-path hour peek; remains for gutter clicks)

## 1. Problem recap

React Big Calendar's day grid is 1D (vertical time only). Actual/tracked data
(desktop sessions + sleep) is bursty, overlapping, and often merges into long
blobs (e.g. "ACShadows · 2h35m · 16 sessions"). A single full-width event strip
per item can't represent:

- multiple overlapping sources within one hour
- where inside an hour something actually ran
- a single long session whose *concurrency* changes hour to hour

Plan blocks stay on the classic RBC grid. Only tracked/actual gets the new
per-hour 2D surface (toggle on Day view). Month/week, the Google→Amazfit
bridge, and tracker collection are unchanged — this is a rendering layer only.

## 2. Data model

### 2.1 `hour_slice` (backend-computed, not frontend-computed)

For each local calendar day in the overlay range, for each hour `h` (0–23) that
has activity (or optionally all 24 — empty hours may be omitted):

```ts
type HourSlice = {
  date: string;              // YYYY-MM-DD local
  hour: number;              // 0-23
  segments: SessionSegment[];
  lane_count: number;        // max concurrent lanes needed this hour
};

type SessionSegment = {
  session_group_id: string;  // merge-group id — same across hours this run spans
  source: "desktop" | "sleep" | "plan_actual";
  app_or_label: string;      // "Sleep" for wearables; short app name otherwise
  category: string;
  start_min: number;         // 0–59 inclusive, clipped to this hour
  end_min: number;           // 1–60 exclusive upper bound inside the hour
  lane_index: number;        // 0-based, STABLE across hours (see §3.2 + sleep)
  total_lanes_this_hour: number; // = hour_slice.lane_count
  session_ids: string[];     // underlying raw session ids for detail popover
  duration_min: number;      // end_min - start_min (for overflow ranking)
};
```

Frontend decides **how to draw** a slice, never **what** it contains (no
overlap math, no lane assignment, no merge).

### 2.2 Real API path (do not invent)

There is **no** `GET /days/{date}/calendar` in this repo.

Tracked overlay lives at:

```http
GET /api/planner/overlay/actual?from=<ISO>&to=<ISO>
```

Today returns `{ "sessions": ActualSession[] }`.

**Change:** attach `hour_slices: HourSlice[]` to that same response:

```json
{
  "sessions": [ /* unchanged */ ],
  "hour_slices": [ /* new */ ]
}
```

Reuse the same session list / sleep bout collection already in
`backend/planner/router.py` → `overlay_actual`. Compute slices in
`backend/planner/hour_slices.py` (pure functions + unit tests). Do not
duplicate tracker DB queries.

### 2.3 `session_group_id` = calendar merge key (not raw session id)

Same merge used by the frontend calendar today
(`mergeForCalendar` / `mergeAdjacentIntervals`):

- Key: `app:{app_name}` or `cat:{category}` (lowercased)
- Contiguous stitch when same key and gap ≤ **900s** (`CALENDAR_MERGE_GAP_SEC`)
- Noise apps filtered; desktop merges shorter than **120s** dropped
- Sleep never merged into desktop

`session_group_id` = that contiguous merged run's identity, e.g.
`{merge_key}|{merged_start_iso}` — stable across every hour slice of that run.
Raw `session_id`s stay in `session_ids[]` for popovers.

## 3. Backend: lane assignment

Run once per day, hours in chronological order, over merged desktop+sleep
intervals clipped to each hour's `[0, 60)` minute window.

### 3.1 Per-hour lane assignment (classic interval graph coloring)

1. Sort segments in the hour by `start_min`, then by `session_group_id`
   (stable tiebreak).
2. Greedily assign each segment the **lowest lane index not currently occupied**
   by a segment it overlaps, subject to §3.2 continuity and §3.4 sleep
   reservation.
3. `lane_count` for the hour = max lane index used + 1 (at least 1 if any
   segment exists).

### 3.2 Cross-hour lane stability

Before assigning freely each hour, check: does this `session_group_id` have
an assigned `lane_index` from the previous hour (and is it still active into
this hour)? If yes, and that lane is still free for this segment's minute
range, **pin** it before greedily assigning the rest.

Width may change hour to hour (`total_lanes_this_hour` varies); horizontal
position stays put unless a competing pin forces a move.

### 3.3 Geometry (frontend applies)

- Horizontal: `width = 1 / total_lanes_this_hour`,
  `x_offset = lane_index / total_lanes_this_hour`
- Vertical **inside** the hour cell: `top% = start_min / 60 * 100`,
  `height% = (end_min - start_min) / 60 * 100`
- **Never** draw a full-hour bar for a partial-minute segment

### 3.4 Sleep reserved lane (tighten-up — required for v1)

When **any** sleep segment is present in an hour:

- Sleep always occupies **lane 0** (muted, leftmost)
- Desktop / other sources use lanes **1…n**
- Cross-hour pin continuity for desktop must **skip / respect** reserved
  lane 0 (never pin a desktop group onto 0 while sleep is reserved that hour;
  if a prior pin was 0 from a no-sleep hour, remap to the lowest free ≥ 1)

## 4. Frontend: rendering

### 4.1 Complexity tiers (exact thresholds)

| `lane_count` this hour | Render mode |
|---|---|
| 1 | Simple full-width bar |
| 2 | Side-by-side, equal width, normal labels |
| 3–4 | Compressed side-by-side, abbreviated labels, no icon |
| 5+ | Top **3 by duration** (`duration_min`) + `+N` overflow chip → session list for that hour |

### 4.2 Continuous multi-hour session (stacked rects + seam suppression)

- One absolutely-positioned rect per `SessionSegment` inside its hour cell
- Same `session_group_id` → same fill + shared left/right border style
- At the seam between two vertically stacked segments of the **same**
  `session_group_id`: suppress `border-radius` and the horizontal border on
  the shared edge so the stack reads as one continuous shape
- Outermost top/bottom of the whole span keep rounded corners
- Defer true SVG polygon paths to a later polish pass

### 4.3 2D mode vs RBC (tighten-up — required)

When **2D track mode is on** (Day view):

- **Hide** RBC **actual** events (no double-paint)
- **Keep** RBC **plan** (and draft) events
- Show `DayGridActualLayer` over the day column

When off: existing RBC actual rendering unchanged.

### 4.4 Click / detail

Clicking a segment (or `+N`) opens existing session-list detail / hour-peek
spirit, scoped to that segment's `session_ids` (or all hidden lanes' ids for
overflow).

## 5. Component boundaries

Under `src/components/productivity/`:

| Component | Responsibility |
|---|---|
| `HourSliceProvider` | Holds `hour_slices` for the visible day from overlay fetch; no layout math |
| `HourCell` | One `HourSlice` → tier (§4.1) + segment layout |
| `SegmentBlock` | One `SessionSegment` → rect + seam flags (§4.2) |
| `DayGridActualLayer` | Positions `HourCell`s; toggles against RBC actuals |

CSS: extend `src/styles/planner-calendar.css` (dark glossy, match existing).

## 6. QoL — ship vs defer

**Ship with core (this pass):**

1. Sleep reserved lane 0 (muted leftmost) — §3.4  
2. Category color legend in day header  
3. Duration-weighted top-3 + `+N` overflow (tier 5+)

**Defer until core is stable:**

4. Empty-hour compression  
5. Optional single-hour focus modal (full-width labeled lanes)  
6. SVG polygon outline for multi-hour shapes

## 7. What stays exactly as-is

- Month / week views (no 2D layer)
- Google Calendar → Zepp/Amazfit bridge
- Desktop tracker session collection
- Plan block CRUD / drag-and-drop (classic RBC)
- No sleep DB wipe; no Google Calendar panel moves

## 8. Build order

1. Backend: `hour_slices.py` + stable lanes + sleep reservation; attach to
   `GET /api/planner/overlay/actual`; unit tests for lane stability
2. Frontend: `HourCell` / `SegmentBlock` tiers 1–2
3. Tiers 3–4 and 5+ (compressed + duration-weighted overflow)
4. Seam suppression (§4.2) + Day toggle (hide RBC actuals)
5. QoL: sleep lane styling + category legend

## Verification

- Unit tests: pin continuity across hours; sleep forces lane 0; desktop skips 0
- Quick typecheck / build of touched TS if feasible
- Manual: Day view → enable “2D track” → overlapping desktop + sleep readable;
  plan blocks still DnD; week/month unchanged
