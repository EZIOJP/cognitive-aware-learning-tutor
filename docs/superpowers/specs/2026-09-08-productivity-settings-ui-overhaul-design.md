# Productivity Settings UI overhaul — design

**Date:** 2026-09-08  
**Status:** Implemented in React (2026-09-08) — Figma can refine polish on the same IA  
**Approach:** C — Figma-ready brief + React restructure in Focus/Study  
**Shipped:** `ProductivitySettingsHub` (G0–G7 one section at a time), quiet primitives, policy `variant` split, `dist-focus` rebuilt.  
**Copy source of truth:** [docs/BLOCKING_RULES.md](../../BLOCKING_RULES.md)  
**Layout ownership today:** [architecture note](../exports/2026-09-08-productivity-settings-architecture-note.md)  
**Parked (not this pass):** [Plan/Calendar/Watch → C++](../exports/2026-09-08-future-plan-calendar-watch-cpp.md)

---

## 1. Goal

Make Productivity **Settings** explainable and maintainable:

- **Grouped** by job (SoftLand sites ≠ Arm apps ≠ unlock ≠ scores ≠ tools).  
- **Disassembled** — each setting gets the control that expresses it (not a wall of checkboxes).  
- **Communicated** — one short sentence of *what this does* next to every control; SoftLand ON ≠ Arm forever.  
- **Minimal** — hide or demote inert knobs; one place for each fact (daily goal lives once).  
- **Quiet components** — purpose-built UI when the setting needs it (week calendar for schedules, host chips for lists, arm/disarm as a clear kill switch).

Success: you can open Focus → Settings and explain SoftLand, Arm, lists, schedules, and unlock without reading the code.

Non-goals this pass: rewrite Plan/Calendar into C++; new SoftLand rules; Figma pixel-perfect theming beyond structure + clarity.

---

## 2. Navigation model

**One Settings surface** (`/productivity?tab=settings` and Focus deep-link `?tab=settings`), with:

| Piece | Behavior |
|-------|----------|
| **Left (or top) group nav** | Sticky: Overview · Now · Sites · Apps · Unlock · Productive · Filters · Tools |
| **Main column** | One **group at a time** (URL hash or `?section=`). Default: **Overview**. |
| **Not** | One mega-scroll of every panel (current pain). |

Switching group replaces the main column; no dumping Focus + Policy + Rules + Watch on one page.

Deep links stay: `#sites`, `#apps`, `#unlock`, etc. Tray “Open Settings” → Overview or last section.

---

## 3. Groups (disassembled)

### G0 — Overview (story, not a dump)

| Block | Content |
|-------|---------|
| Two weapons | SoftLand = sites · Arm = apps — never confuse |
| Status strip | SoftLand on/off · Armed/Disarmed · mode · until (native as-of OK) |
| Jump cards | Sites · Apps · Unlock · Productive |
| Offline note | SoftLand/Arm/lists/schedules work without `:8000`; scores/filters/watch need API |

No editors here except SoftLand master toggle (optional) and link into Now for Arm.

### G1 — Now (Focus)

Live SoftLand mode / why / until · earned balance · spend · incubation card · **Arm / Disarm** + lock mode summary.

Kill-list *preview* only; full editor is **Apps**. Site lists → **Sites**.

### G2 — Sites (SoftLand)

| Setting | Quiet component | Copy (from BLOCKING_RULES) |
|---------|-----------------|----------------------------|
| SoftLand on/off | Single clear switch + “does not Arm” | Master site switch |
| Allow extra | Host chip list + add | Always allowed; beats porn filter |
| Watch extra | Host chip list + add | Study only; free/reward lets through |
| Block extra | Host chip list + add | Every mode, including reward day |
| Schedules | **Week strip + time windows** (mini calendar / Mon–Sun day toggles + start–end + mode) | First matching window wins; empty days = all days |
| Mode flags | Only **block_porn** + **block_watch_sites** | Hide or collapse inert: social / keywords / other / strict_allowlist with “not used by decide today” |

Built-in watch list: read-only chip cloud (“always in study when watch blocking on”) — not editable; override via Allow.

### G3 — Apps (Arm)

| Setting | Quiet component |
|---------|-----------------|
| Kill list | Executable list + add (`discord.exe`) |
| Arm / Disarm | Primary danger/safe actions (same as Now) |
| Lock mode | Segmented: none / timer / password / phrase + fields |
| Anti-tamper / protect uninstall | Toggles with one-line consequence |

Never mix SoftLand host lists into this group.

### G4 — Unlock (commitment & escapes)

| Setting | Quiet component |
|---------|-----------------|
| Daily goal (minutes) | Number + link “same as Plan daily focus” — **single writer** |
| Day pass | Status (used/limit) + confirm phrase field `PASS` |
| Reward day | Credits available + confirm `REWARD` |
| Study Loop gate | On/off + short “forces morning into bite when on” (default off) |
| Earned minutes | Balance + spend control (or deep-link Now) |

Honest badges: **Needs API** until P5a; SoftLand free window after claim still via gateway where wired.

### G5 — Productive (what counts)

Threshold · productive/blocked categories · score sliders · app overrides · session override.

Badge: **Needs API**. Keep scoring tools here; pull them out of SoftLand policy mega-panel.

### G6 — Filters (PC-wide)

Hosts porn block (and optional watch/social hosts). Separate card: “all apps, needs admin, ≠ SoftLand porn heuristic.”

### G7 — Tools

Demo clock (with **day calendar** jump) · Watch sync · Reminders · Export · Setup docs.

---

## 4. Quiet component kit (minimal, reusable)

Build small, named pieces under `src/components/productivity/settings/` (or similar):

| Component | Expresses |
|-----------|-----------|
| `SettingSection` | Title + one-line why + optional “Needs API” / “Native” badge |
| `SettingRow` | Label · control · consequence text (never label alone) |
| `HostChipEditor` | Allow / Watch / Block lists |
| `ExeChipEditor` | Kill list |
| `ScheduleWeekEditor` | Days + windows (calendar-like week, not raw JSON) |
| `ModeFlagSwitches` | Only live SoftLand flags |
| `ConfirmPhraseField` | PASS / REWARD |
| `NativeOrApiBadge` | Offline-native vs API-required |
| `WeaponCallout` | SoftLand vs Arm (Overview + Sites/Apps headers) |

**Rule:** if the setting is temporal → show a calendar/week/time control. If it is a host → chips. If it is Arm → kill switch + exe list. Do not reuse a generic form for everything.

---

## 5. Copy & honesty rules

1. SoftLand ON ≠ Armed — every Sites and Apps header.  
2. Watch vs Block — exact BLOCKING_RULES wording (study-only vs every mode).  
3. Inert flags — do not present as active; collapse under “Advanced (unused by engine)”.  
4. One daily goal — Settings Unlock owns the number; Plan shows read-only or syncs same field.  
5. Day pass honesty — until P5a, note that pass may not unlock sites (or fix P5a first if owner prefers). Prefer UI note over silent failure.

---

## 6. Figma brief (same IA)

Frames to produce (or mirror in React first):

1. Overview  
2. Now  
3. Sites (lists + schedule week)  
4. Apps (Arm)  
5. Unlock  
6. Productive (API badge)  
7. Filters  
8. Tools  

States: SoftLand off · SoftLand on study · free/reward · incubating · Armed · API down (scores greyed).

Dark Focus shell; keep CALT gloss — no purple-dashboard cliché; minimal chrome.

---

## 7. Implementation shape (after spec approval)

1. Add section router on Settings (`section` query or hash).  
2. Split `ProductivityPolicyPanel` into Sites / Unlock / Productive / Filters pieces.  
3. Move schedules + site lists under Sites; kill list under Apps; Focus panel under Now.  
4. Introduce quiet components; replace raw dumps.  
5. `npm run build:focus` so `calt_focus` picks up `dist-focus`.  
6. No new gateway ops required for layout (use existing Phase 2 ops).

---

## 8. Out of scope

- P5 unlock migration to C++  
- Plan/Calendar/Watch full native store  
- Redesigning Calendar/Plan tabs (only Settings)  
- Changing SoftLand decide ladder (except already-shipped schedule/timezone fixes)

---

## 9. Approval checkpoint

Owner: confirm this IA (groups G0–G7 + quiet components + one-section-at-a-time nav).  
Then: implementation plan → React + Focus build.
