# Shutdown Ritual — Implementation Plan (deferred)

**Goal:** Sunsama-style **end-of-day shutdown**: review plan vs actual, carry open tasks, optional journal line, arm tomorrow mode.

**Architecture:** React wizard on Productivity Calendar (after 6pm or manual). Reads adherence + planner blocks; writes carry-forward via existing planner APIs. No new backend tables in v1.

---

### Scope (when scheduled)

**Files (planned):**
- Create: `src/components/productivity/ShutdownRitualPanel.tsx`
- Modify: `ProductivityPage.tsx` — Calendar tab CTA
- Modify: `MorningAutoPlanPanel.tsx` — surface carried tasks

**Steps:**
1. Show today pulse + on-plan focus vs goal
2. List incomplete planner blocks → “move to tomorrow” / “drop”
3. Extra goals checkbox review
4. Optional one-line reflection (localStorage)
5. Confirm → set browser mode planning for next open

**Out of scope v1:** email digest, team sharing.

**Prerequisite:** Pulse + goals status (implemented in prior plans).

**Verify:** visual QA on Calendar tab
