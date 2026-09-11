# Settings Make visual melt-in — Implementation Plan

> **For agentic workers:** Use executing-plans or implement task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Restyle Make Settings to theme tokens + gloss so it melts into Calendar/Plan in light and dark.

**Architecture:** Approach 1 — class-only restyle of `MakeSettingsApp.tsx` and `ProductivitySettingsTab.tsx` wrapper. IA and demo logic unchanged.

**Tech Stack:** React, Tailwind theme tokens, `gloss-panel` from `src/styles/glossy.css`

## Global Constraints

- SoftLand ON ≠ Armed copy stays.
- No live gateway wiring.
- No Approach 3 shadcn rebuild.
- Light + dark via tokens only (no hardcoded `#0f0f0f` shell).

---

### Task 1: Wrapper + primitives + shell

**Files:** `ProductivitySettingsTab.tsx`, `MakeSettingsApp.tsx`

- [x] Wrapper → `gloss-panel rounded-3xl border border-border/50 bg-background`
- [x] Restyle Badge, Toggle, Card, SectionHeader, SettingRow, DayPills
- [x] Restyle aside/nav/footer + root (drop Inter)

### Task 2: Section surfaces

- [x] Overview, Rules, Unlock, Productive, Tools — theme tokens on cards, inputs, buttons, tabs

### Task 3: Verify

- [x] `npm run build:focus`
- [ ] Spot-check Settings in UI / Focus Update UI
