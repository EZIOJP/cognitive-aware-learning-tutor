# Focus Rhythm Design

**Goal:** Make Calendar analytics understandable at a glance by showing when focused work happened, when planned time was interrupted, and the sources of those interruptions.

## Scope

Add a Focus Rhythm panel inside the existing Calendar-tab Plan vs actual section. It follows the Calendar's selected day and view:

- **Day:** buckets activity by local hour.
- **Week:** buckets activity by Monday through Sunday.
- **Month:** buckets activity by calendar day.

The panel tells one consistent story:

1. A headline names the strongest focus bucket and the strongest interruption bucket.
2. A three-part balance shows:
   - **In the zone:** productive tracked time overlapping a planned block.
   - **Pulled away:** low-score tracked time overlapping a planned block.
   - **Focused elsewhere:** productive tracked time outside planned blocks.
3. A stacked time-pattern chart shows green zone minutes and rose pulled-away minutes for each bucket.
4. A short list identifies the most frequent low-score app/site sources in the selected range.

## Data and calculations

Reuse the existing Calendar data only:

- Planner blocks from `usePlannerBlocks`.
- Tracked sessions from `useActualOverlay`.
- The active productivity score threshold from the existing session payload (`productivity_score >= 60`).

Each session is clipped to the selected range and split at planned-block boundaries. Its elapsed minutes are classified as zone, pulled-away, focused elsewhere, or neutral. The focus rhythm only displays the first three classifications. Sessions without valid timestamps, sleep, or zero elapsed time are ignored.

## UX rules

- Use everyday labels; technical terms such as “adherence” stay in the existing heatmap rather than replacing the new labels.
- Do not claim a distraction source when there is no low-score time.
- Preserve the Calendar's existing Day / Week / Month controls; do not add another range selector.
- For sparse data, explain the next action: add planned blocks and keep the tracker running.
- Reuse the existing dark gloss panels, Recharts styling, responsive layout, and accessible chart labels.

## Boundaries

- No new backend endpoint or persistence.
- No new analytics route or separate dashboard.
- No gate, wearable, SRS, or quiz behavior changes.
- The panel is derived client-side from existing planner and tracker data.
