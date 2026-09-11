# Settings intuitive UX — brainstorm + architecture handoff

**Date:** 2026-09-09  
**Status:** Brainstorm locked · design/spec next · **no implementation yet**  
**Audience:** Owner + agents + Figma pass  
**Figma Design (MCP-writable):** [CALT Productivity Settings](https://www.figma.com/design/dh3NXL3H3UoZ6FRDcmDClj)  
**Figma Make (not MCP-accessible):** [User-introduction](https://www.figma.com/make/L4vfqkZuaL2ud7AmmklrUB/User-introduction) — copy frames into Design if needed  

**Related**

| Doc | Role |
|-----|------|
| [BLOCKING_RULES.md](../../BLOCKING_RULES.md) | Rule source of truth for copy |
| [Settings UI overhaul design](../specs/2026-09-08-productivity-settings-ui-overhaul-design.md) | IA shipped (G0–G7 groups) |
| [Architecture note](2026-09-08-productivity-settings-architecture-note.md) | Layout ownership (partially superseded by this handoff) |
| [After P5a](2026-09-09-after-p5a-next.md) | Native unlock roadmap (orthogonal) |

This **export** is the single place that ties: decisions → Settings changes → architecture/rules → React components → Figma → what “export” means in-product.

---

## 1. Questions asked → answers locked

| # | Question | Answer |
|---|----------|--------|
| 1 | Who is the naive user? | **Everyone** — UI must be understood without CALT jargon |
| 2 | Remove Focus page? | **Yes (retire duplicate).** Focus mega-panel ≈ Settings → Now. Redirect Focus → Settings Overview; drop JSON/PID dump for normal users |
| 3 | Overview “time left / what’s next”? | **B — today’s Plan block** (current task + next). SoftLand/Arm = short “what’s blocking now” strip, not the cycle clock |
| 4 | Ship how? | **A — one big pass** (Overview + retire Focus + rewrite every Settings group). **No Tools search** |
| 5 | Figma workflow? | **Figma-first (Approach 1)** in Design file, then React matches. Make files cannot be read by MCP |
| 6 | Bible skip day-pass? | **Removed from UI** (2026-09-09). Unlock doors = goal+Bible **or** reward day. Backend `/api/bible/day-pass` still exists unused by UI |
| 7 | Make zip / credits | Figma Make export unzipped under `.tmp-user-introduction/` (reference only). Rebuild in Design file + React — do not treat Make as SoT |
| 8 | Sites vs Apps UX | Owner rejects separate chip walls. **Rules** = combined block list (site / app / porn-hidden) |
| 9 | Now tab | **Remove.** Non-duplicated controls move to **Overview** (earn/spend, Arm/Disarm, live mode) |
| 10 | Filters tab | **Remove.** Porn is a **permanent system row** inside Rules (not a hobby settings page) |
| 11 | Tools | **Subdivide:** Watch Sync = own tab/page; Export = own tab/page; Tools keeps demo / reminders / setup |
| 12 | Mode-column table | **After** nav reshape. Unified list with type tags + study/free/reward columns (SoftLand hosts vary by mode; Arm kills whenever Armed) |

---

## 2. What we are changing (product shape)

### Before (pain)

```text
Productivity tabs: Calendar | Plan | Settings | (Focus page / Enforcer dump)
Settings: Overview · Now · Sites · Apps · Unlock · Productive · Filters · Tools
Focus / Now: duplicate live SoftLand + Arm + technical dump
Sites vs Apps: two chip editors — hard for naive users
Filters: porn as a separate “job”
Tools: Watch + Export buried as cards
```

### After (target) — synced to Make zip `(1)` 2026-09-09 03:25

```text
Productivity tabs: Calendar | Plan | Settings
Settings nav (5):
  Overview  — weapons · mode strip · Plan now · earn · Arm/DISARM
  Rules     — Block list | Schedules sub-tabs · mode columns · system filter
  Unlock    — goal · reward · Study Loop
  Productive— scores (API)
  Tools     — sub-tabs: Watch sync | Export | Other
Focus route → ?tab=settings&section=overview
```

Make prototype path: `.tmp-user-introduction-v2/` · canvas mirrors it (filter wording, no gaming presets).

---

## 3. How pieces work together

### 3.1 Product architecture (locked)

```text
USER INTENT (Plan goals + day blocks)
        │
        ▼
┌───────────────────┐     ┌────────────────────┐
│ CALT Study :8000  │     │ CALT Productivity  │
│ notes · Bible     │     │ C++ enforcer       │
│ Plan content APIs │     │ SoftLand msg-host  │
│ unlock ledgers*   │     │ calt_focus UI      │
└─────────┬─────────┘     └─────────┬──────────┘
          │                         │
          │  goal minutes / reward  │  softland_policy.json
          │  (until P5a)            │  enforcer_policy.json
          └────────────┬────────────┘
                       ▼
              Edge Gate asks get_mode
              Enforcer kills listed .exe when Armed
```

\*Python still owns reward-day / earned minutes until P5a; SoftLand decide + kills never need Python live.

### 3.2 Two weapons (rules the UI must teach)

| | SoftLand | Arm |
|---|----------|-----|
| Blocks | Websites (Edge Gate) | Apps (OS kills) |
| Switch | `softland_enabled` | `hard_block_armed` |
| UI home | Sites + Overview strip | Apps list + Now Arm |
| Never | Kill Steam | SoftLand a URL |

**SoftLand ON ≠ Armed.** Copy and Overview must say this every time.

Full ladder: [BLOCKING_RULES.md](../../BLOCKING_RULES.md).

### 3.3 Overview clock = Plan productivity (answer B)

| Layer | Source | Shows |
|-------|--------|-------|
| **Cycle** | Plan / calendar blocks for today | Current task title · end time · minutes left · **Next** task |
| **Goals** | Plan daily focus ↔ SoftLand `daily_goal_minutes` | Progress toward unlock (minutes) |
| **Blocking now** | SoftLand decide + Arm status | Mode (study/free/…) · one-line why · Armed? |
| **Rules summary** | Derived from mode + lists | Plain bullets: “Watch sites blocked · Steam killed if Armed” — not JSON paths |

Plan owns **what you should be doing**. SoftLand/Arm own **what the machine enforces**. Overview shows both without mixing editors.

### 3.4 Unlock doors (after day-pass removal)

| Door | User action | UI |
|------|-------------|-----|
| Earn | Hit daily goal **and** 1 Bible chapter | Unlock status |
| Reward day | Bank 4 qualifying days → claim | Unlock · confirm REWARD |
| ~~Day pass skip Bible~~ | ~~Removed~~ | — |
| Earned minutes | Chores → spend 15m chunks | Now · Spend |

---

## 4. Settings groups ↔ code components ↔ rules

| Section | Job (plain) | React today → target | Rule / store |
|---------|-------------|----------------------|--------------|
| **Overview** | Plan cycle · mode · Arm · earn/spend | Hub story + **absorb** `FocusControlPanel` (slim) | Plan day API + SoftLand status + Arm |
| **Rules** | One block list: site / app / porn-system | Merge `SoftLandSiteRulesPanel` + `AppKillRulesPanel` + schedules + SoftLand master; porn from `DeviceBlockPanel` as hidden system row | SoftLand decide + enforcer kills; porn heuristic/hosts |
| **Unlock** | Goal · Bible · reward | `ProductivityPolicyPanel` unlock (no day-pass UI) | Bible/gate unlock (API until P5a) |
| **Productive** | What counts toward goal | `ProductivityPolicyPanel` scoring | Category scores / threshold (API) |
| **Watch** | Wearable sync | Extract from Tools | Watch sync APIs |
| **Export** | Week / activity export | Extract from Tools | Export APIs |
| **Tools** | Demo · reminders · setup | Leftover panels | Demo clock etc. |

**Removed nav:** Now · Sites · Apps · Filters (as tabs).

**Primitives:** `src/components/productivity/settings/SettingPrimitives.tsx`  
**Hub:** `ProductivitySettingsHub.tsx` — rewrite NAV ids  
**Duplicate Focus:** `FocusPage.tsx` → redirect Overview; slim live controls on Overview only.

---

## 5. Figma ↔ agent collaboration

| Surface | MCP? | Use |
|---------|------|-----|
| `/design/dh3NXL3H3UoZ6FRDcmDClj` | **Yes** | Source of truth for screens; agent builds/edits frames |
| `/make/L4vfqkZuaL2ud7AmmklrUB` | **No** | Inspiration only — paste into Design or screenshot |
| React `dist-focus` | — | Implement after Figma approval |

**Workflow (Approach 1)**

1. Spec approved (this handoff → full design doc).  
2. Figma: redesign Overview cockpit + every group (plain language).  
3. Owner eyeballs Figma.  
4. React matches frames; Focus redirects; `build:focus`.  
5. Copy stays aligned with BLOCKING_RULES (update day-pass section when implementing).

---

## 6. What “export file” means (three layers)

| Layer | Path / artifact | Purpose |
|-------|-----------------|--------|
| **This handoff** | `docs/superpowers/exports/2026-09-09-settings-intuitive-ux-handoff.md` | Decisions + architecture map for agents/owner |
| **Design spec (next)** | `docs/superpowers/specs/2026-09-09-settings-intuitive-ux-design.md` | Approved UI design before code |
| **In-app Tools → Export** | Settings → Tools → export week/activity | User data export — **unchanged** this pass; keep findable, no new search |

Do not confuse agent export docs with the Productivity **Export** tool panel.

---

## 7. Success criteria

A naive user can open Settings → Overview and answer without reading code:

1. What am I supposed to be doing **right now**? (Plan block)  
2. When does this block end / what’s next?  
3. Are sites or apps being blocked, and **why** (one sentence)?  
4. Where do I change SoftLand lists vs kill list vs daily goal?  

Focus page no longer exists as a second cockpit.

---

## 8. Next steps (brainstorm checklist)

1. ~~Questions~~  
2. ~~Approaches (Figma-first A)~~  
3. **Present design sections** → owner approve  
4. Write formal **design spec** + self-review  
5. Owner reviews spec  
6. **writing-plans** → implement (Figma then React)

---

*End of export.*
