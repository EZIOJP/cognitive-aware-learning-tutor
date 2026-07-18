# Plan tab completion — multi goals + finish flow

**Date:** 2026-07-18  
**Approved:** Option A — main goal + addable extra goals/todos

## Flow

1. **Goals** — main + extras
2. **Routines & timetable** — daily rhythm / import first
3. **Propose week** — AI from goals + tracker
4. **Finish** — apply + open calendar

## Goals model (`productivity:goals:v1`)

```ts
{
  mainGoal, focusHoursPerDay, weeklyFocusHours, reward,
  extraGoals: { id, title, done }[]
}
```

Extras feed the propose prompt as a bullet list. Primary focus hours stay on main goal only.
