# Productivity Settings UI overhaul — implementation plan

> **For agentic workers:** Execute task-by-task. Owner approved “complete everything” 2026-09-08.

**Goal:** Grouped Settings (G0–G7), one section at a time, quiet components, BLOCKING_RULES copy.

**Spec:** [2026-09-08-productivity-settings-ui-overhaul-design.md](../specs/2026-09-08-productivity-settings-ui-overhaul-design.md)

## Tasks

1. Kit: `SettingSection`, `SettingRow`, `NativeOrApiBadge`, `WeaponCallout`
2. `ProductivitySettingsHub` — section nav + mount groups
3. Wire `ProductivityPage` settings tab to hub; pass page-owned Tools/Scoring/Export slots
4. `ProductivityPolicyPanel` `variant`: `unlock` | `scoring` | `softland` | `all`
5. Improve `GateSchedulesPanel` week-day UI label as schedule calendar strip
6. `npm run build:focus`; update design status to implementing/done

No new gateway ops.
