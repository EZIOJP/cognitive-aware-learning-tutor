# Life Clock skins implementation plan

> **For agentic workers:** Execute task-by-task. Classic + Omnitrix Pour only.

**Goal:** Skin switcher + Omnitrix hourglass pour face on LifeClockWidget.

**Spec:** `docs/superpowers/specs/2026-07-18-life-clock-skins-design.md`

## File map

| File | Role |
|------|------|
| `src/components/hub/lifeClockSkins.ts` | Skin ids, labels, localStorage load/save |
| `src/components/hub/LifeClockOmnitrixFace.tsx` | Omnitrix Pour SVG + triangle info |
| `src/components/hub/LifeClockWidget.tsx` | Wire skins, picker, keep Classic ring |

## Tasks

### Task 1: Skin persistence helpers
Create `lifeClockSkins.ts` with `LifeClockSkinId = "classic" | "omnitrix"`, load/save.

### Task 2: Omnitrix face
Hourglass clip + vertical litmus bands + green bezel + triangle HTML overlays.

### Task 3: Widget integration
Picker UI; render Classic vs Omnitrix; stopPropagation on controls.
