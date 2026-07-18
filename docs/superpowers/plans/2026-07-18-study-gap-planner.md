# Study Gap Planner Implementation Plan

> **For agentic workers:** Use executing-plans or implement task-by-task. Checkboxes track progress.

**Goal:** Finish Approach C — ~50m gap packing to daily goal, adherence load adjust, visual reward unlock.

**Architecture:** Deterministic packer in `llm_propose.py` is primary; router passes busy blocks + adherence; FE shows reward unlock on Plan/Today.

**Tech Stack:** FastAPI, Python packer, React Productivity UI, pytest

## Global Constraints

- Study chunks ~50m; break after chunk; stop at daily goal; no gaming-as-study
- Adherence last-7d: ≥80% → 100% load, 60–80% → 90%, &lt;60% → 80%
- Visual “Reward unlocked” when effective focus ≥ daily goal

---

### Task 1: Gap packer (~50m + breaks + ceiling)

**Files:** `backend/planner/llm_propose.py`, `tests/test_productivity_policy.py`

- Prefer 50m study chunks; insert short breaks; cap continuous study ~100m
- Stop when planned study ≥ target daily minutes (do not overfill)
- Report shortfall in rationale when gaps &lt; goal

### Task 2: Adherence load scale

**Files:** `backend/planner/llm_propose.py`, `backend/planner/router.py`

- Compute study adherence from last ~7 days export/adherence
- Scale daily target before packing; surface adjust in rationale/badge

### Task 3: Visual reward unlock

**Files:** `ProductivityGoalsPanel.tsx` / `TodayPanel.tsx` / Plan Finish step

- When today’s effective focus ≥ daily goal, show clear “Reward unlocked” + Goals.reward copy

### Task 4: Verify

- pytest packing / no gaming / breaks / adherence scale
- Manual: Build smart → apply → hours badge honest
