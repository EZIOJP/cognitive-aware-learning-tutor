# Calendar hour peek (safe path)

**Date:** 2026-07-26  
**Status:** Implementing (safest slice only)

## Goal

Make plan-vs-actual calendar readable and trustworthy without experimental 2D / horizontal polygon layouts.

## In scope

1. **Sleep label** — chips say `Sleep`, never `Amazfit`.
2. **Focus overflow** — clicking a block must not spill the day column outside the calendar card (`overflow-hidden`; popup stays inside / clipped cleanly).
3. **Hour peek** — click a left gutter hour → panel lists apps/sleep for that hour on the focused calendar day.

## Out of scope (rollback / later)

- Horizontal “second dimension” strips or freeform polygons inside hour cells.
- Drag-resize of actual tracker blocks.

## Rollback

Hour peek is UI-only in `PlannerCalendar` + small helpers in `planVsActualUtils`. Revert those diffs; no schema/API change.
