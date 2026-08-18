# Activities Inbox — Implementation Plan

**Goal:** RescueTime-style ranked **Activities** list — apps and browser sites with time, category, score, and uncategorized flag.

**Architecture:** Flatten `AppBucket` / `SiteBucket` from `stats_aggregate` into `activities_payload()`. New GET endpoint; React panel in Settings tab.

---

### Task 1: Backend payload

**Files:**
- Modify: `backend/behavior/stats_aggregate.py` — `activities_payload(buckets)`
- Modify: `backend/behavior/router.py` — `GET /api/behavior/activities?day=`

**Activity shape:**

```json
{
  "key": "youtube.com",
  "label": "youtube.com",
  "kind": "site",
  "seconds": 1800,
  "category": "Video Streaming",
  "productivity_score": 15,
  "uncategorized": false
}
```

Uncategorized when category is `Other` / `Other (Browser)` and no app override.

- [ ] Sort by seconds desc; optional `?uncategorized_only=1`
- [ ] Reuse same session query path as desktop-stats

### Task 2: Frontend panel

**Files:**
- Create: `src/components/productivity/ActivitiesPanel.tsx`
- Modify: `src/api/behaviorClient.ts` — `fetchActivities(day?)`
- Modify: `src/pages/ProductivityPage.tsx` — Settings tab, above ClassificationReview

- [ ] Table: label, time, category, score chip
- [ ] Filter toggle: All / Uncategorized
- [ ] Link hint: “Fix in Classification review below”

### Task 3: Tests

- Create: `tests/test_activities_api.py`

**Verify:** pytest + build
