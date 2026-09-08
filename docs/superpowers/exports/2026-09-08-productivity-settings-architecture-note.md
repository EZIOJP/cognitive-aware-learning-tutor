# CALT Productivity — Settings / Plan / Calendar / Focus / Blocking (architecture note)

**Date:** 2026-09-08  
**Audience:** Owner + agents  
**Related:** [solo pack design](../specs/2026-09-08-calt-productivity-solo-pack-design.md) · [product lock](../specs/2026-09-07-calt-productivity-cpp-product-design.md) · [SoftLand state](../specs/2026-09-07-calt-productivity-softland-state-model.md)

This note is the map of **what lives where** in the Productivity UI and how blocking actually runs. It is not a Settings redesign plan (that stays a separate IA pass).

For the **rule-by-rule behaviour** — the SoftLand ladder in evaluation order, which
mode flags are inert, which lists survive a reward day, and the sharp edges — see
[docs/BLOCKING_RULES.md](../../BLOCKING_RULES.md). That file is the source of truth
for Settings copy; this one is the source of truth for layout and ownership.

---

## 1. One product, three tabs + Focus door

Same React UI in the browser Study app **and** in `calt_focus.exe` (WebView2 → `dist-focus/`).

| Surface | Route | Job |
|---------|-------|-----|
| **Calendar** | `/productivity` (tab Calendar) | Day view: blocks, day status, incubation toasts, screen-time glance |
| **Plan** | `/productivity?tab=plan` | Routines, **Goals**, Apply my day, build week |
| **Settings** | `/productivity?tab=settings` | SoftLand / Arm / lists / scores / tools (long scroll + anchors) |
| **Focus** | `/productivity/focus` or Settings `#focus` | Live SoftLand mode + earn/spend + **Arm / Disarm** (tray deep link) |

Study system Settings (`/settings` theme/AI/plugins) is a **different** product surface — not SoftLand/Arm.

```text
YOU
 ├─ Calendar  …… what happened / what’s on today
 ├─ Plan      …… goals & day shape (feeds SoftLand unlock minutes)
 ├─ Settings  …… configure blocking + scoring + tools
 └─ Focus     …… now-mode + Arm (same FocusControlPanel as Settings #focus)

RUNTIME (solo pack)
 ├─ calt_enforcer   …… OS kills + desktop track + Focus watchdog
 ├─ calt_msg_host   …… SoftLand get_mode + browser track_tab
 └─ Edge Gate / SelfTracker
```

**Naming forever**

- SoftLand ON = sites in Edge (Gate). Does **not** kill Steam.
- Arm = OS process kills (`hard_block_armed`). Does **not** SoftLand URLs by itself.

---

## 2. Two blocking weapons (+ one optional filter)

| System | Blocks | Owner | Store |
|--------|--------|-------|--------|
| **SoftLand** | URLs / modes (study, free, incubation) | Gate → `calt_msg_host` (HTTP `:8000` fallback) | `softland_policy.json` |
| **Arm** | Listed `.exe` | `calt_enforcer` | `enforcer_policy.json` |
| **Hosts porn-block** (optional) | Adult / optional YT/social via Windows hosts | Python API | device-block — **not** the SoftLand/Arm core story |

Intended day loop (SoftLand stateful):

```text
Bible → plan confirm → (optional Study Loop) → daily productive goal
  → day-unlimited / day-pass / reward-day
  → earn ledger → spend / PIN free
  → incubation (mandatory boring break; blocks PIN free)
```

---

## 3. Calendar — what it is

**Purpose:** See the day; not the main place to edit SoftLand rules.

Typical content:

- Day agenda / planner blocks  
- Day status (gate / SoftLand glance)  
- Incubation / free windows when active  
- Screen-time / tracked sessions (from SQLite + SelfTracker / enforcer)

**Does not own:** kill list editor, SoftLand site CRUD, Arm button (those are Focus / Settings).

---

## 4. Plan — what it is

**Purpose:** Shape the day and goals that SoftLand treats as unlock inputs.

| Control | Use | Notes |
|---------|-----|--------|
| Routines / Apply my day | Build today’s blocks | May pack study-task allow hosts |
| **Goals & motivation** | Main goal text, daily/weekly focus hours, reward copy | Daily focus hours sync → SoftLand `daily_goal_minutes` |
| Study tasks | Presets (Scaler, GRE, …), minutes, allowHosts | Task-scoped allows ≠ global SoftLand allow list |
| Extra todos | AI propose fodder | LocalStorage |

**Duplicate to remember:** Plan “daily focus h” and Settings `#policy` “Daily goal (min)” are the **same unlock target** — keep one story in UX later.

---

## 5. Focus — what it is

**Purpose:** Live control panel for SoftLand **now** + OS **Arm**.

| Area | Controls |
|------|----------|
| **Now** | SoftLand mode label, why, until, blocked summary, incubation card, earned balance |
| **Actions** | Free time (PIN), Spend earned |
| **Enforcer** | Armed chips, kill-list preview, lock mode, anti-tamper, protect uninstall, **Arm / Disarm** |
| **Related** | Links to Calendar / Study Loop / Bible |

Solo-pack honesty:

- Gate interstitial why/until = **native** (`reason` / `until`).  
- Focus Now why with API down = **frozen** snapshot from `softland_policy.json` (Focus shell `calt-data.app`) — **as-of**, not live ledger.  
- Arm/Disarm UI today still often needs `:8000`; kills keep running from JSON while enforcer is up.

---

## 6. Settings — current sections (as mounted)

Order on `/productivity?tab=settings`:

| Anchor | Label | Panels / controls |
|--------|-------|-------------------|
| Intro | SoftLand vs Arm callout | Copy only |
| `#focus` | Focus / Enforcer | Same as Focus page |
| `#policy` | SoftLand / productivity policy | SoftLand on, Study Loop gate, day-pass, reward day, daily goal min, game-bank exes, productive threshold, category checkboxes, category scores, app overrides, **Device porn block** (nested) |
| `#rules` | Blocking rules | Gate schedules · App kill list · SoftLand allow/watch/block hosts |
| `#planning` | Planning | Auto-apply routines; RO morning / `BROWSER_FREE_AFTER` |
| `#demo-mode` | Demo mode | Fake clock |
| `#watch` | Watch ↔ PC | Wearables |
| `#reminders` | Plan reminders | Browser notifications |
| `#scoring` | Scoring & classification | Session override, activities, LLM classification |
| `#export` | Export | Week / activity export |
| `#setup` | Tracker setup | Install docs (Gate, enforcer, msg-host) |

### Settings inventory by job (sense-making)

**A. Commitment (SoftLand stays on until you earn unlock)**  
SoftLand on · daily goal · Study Loop gate · day-pass · reward day · morning chain (mostly RO / Bible)

**B. Earn → spend**  
Earned balance · Spend · PIN free · incubation (status; config still thin)

**C. SoftLand site lists**  
Allow / Watch / Block extra · recurring schedules · evening free-after (RO / schedules)

**D. Arm (apps)**  
Kill list · Arm/Disarm · lock · anti-tamper · protect uninstall  
*(SoftLand “game-bank exes” are scoring/commitment — not the OS kill list)*

**E. What counts as productive**  
Threshold · productive/blocked categories · scores 0–100 · app overrides · session override / classification

**F. PC-wide filters**  
Hosts porn (+ optional streaming/social) — separate from SoftLand

**G. Tools**  
Demo · wearables · reminders · export · setup scripts

---

## 7. Proposed Settings groups (for a later IA pass)

Do **not** implement this layout in the same pass as native solo-pack. When redesigning, use:

1. **How blocking works** — story + SoftLand on + daily unlock + Study Loop + escapes  
2. **Now / free time** — mode, earned, spend, incubation (Focus home)  
3. **Sites (SoftLand)** — allow/watch/block + schedules  
4. **Apps (Arm)** — kill list + Arm/lock  
5. **What counts productive** — scores / categories / overrides  
6. **PC-wide filters** — hosts porn  
7. **Tools & setup** — demo, watch, reminders, export, install  

Each group should get its **own** panel layout (not one mega-scroll of unlabeled ingredients).

### Data availability (Phase 2 gateway — backend closed 2026-09-08, verified with `:8000` stopped)

| Group | With `:8000` stopped |
|-------|----------------------|
| SoftLand enforce / Gate why | Works (native `get_mode`; HTTP SoftLand fallback **off** by default — Prod P4) |
| Arm kills | Works (enforcer + JSON) |
| Browser + desktop track | Works (msg_host + enforcer) |
| SoftLand **edits** — on/off, allow/watch/block lists, schedules, mode flags, goals, day-pass, reward day, incubation, spend | Works: Focus WebView `enforcer_cmd` → enforcer named pipe → SQLite SoT → JSON mirror |
| Arm **edits** — arm/disarm, kill list, lock mode, anti-tamper | Works: gateway `arm.set` (HTTP PUT remains fallback outside the Focus shell) |
| Earn ledger / clocks | Works: SQLite ledger + enforcer tick (expiry and delayed `pending_changes` apply with no UI open) |
| Scores / classification / category weights / hosts porn-block | **Need API** — Python-owned by design |

So a Figma Settings overhaul can treat SoftLand, Arm, Focus/Now, lists,
schedules and the ledger as **offline-native**, and must keep scores /
classification / hosts on an "API required" affordance.

Owner-side commands for spot-checking either path:

```bat
powershell -File scripts\desktop_tracker\run\gateway_cmd.ps1 -Op status.snapshot
powershell -File scripts\desktop_tracker\run\gateway_cmd.ps1 -Op ledger.snapshot -Payload "{\"limit\":10}"
powershell -File scripts\desktop_tracker\run\msg_host_cmd.ps1 -Json "{\"type\":\"get_mode\",\"url\":\"https://youtube.com\"}"
```

**Spec:** [2026-09-08-calt-productivity-phase2-gateway-design.md](../specs/2026-09-08-calt-productivity-phase2-gateway-design.md)  
**Plan:** [2026-09-08-calt-productivity-phase2-gateway.md](../plans/2026-09-08-calt-productivity-phase2-gateway.md)

---

## 8. Files to open when changing this area

| Concern | Path |
|---------|------|
| Settings host | `src/pages/ProductivityPage.tsx` |
| Focus UI | `src/components/productivity/FocusControlPanel.tsx` |
| SoftLand policy UI | `src/components/productivity/ProductivityPolicyPanel.tsx` |
| Kill list | `src/components/productivity/AppKillRulesPanel.tsx` |
| Site rules | `src/components/productivity/SoftLandSiteRulesPanel.tsx` |
| Schedules | `src/components/productivity/GateSchedulesPanel.tsx` |
| Goals (Plan) | `src/components/productivity/ProductivityGoalsPanel.tsx` |
| SoftLand decide | `native/calt_msg_host/` |
| OS kills | `native/calt_enforcer/` |
| Focus shell | `native/calt_focus/` |
| Gate / SelfTracker | `calt-gate-extension/`, `selftracker-extension/` |

---

## 9. Bottom line

- **Calendar** = day visibility.  
- **Plan** = goals & shape (feeds SoftLand unlock).  
- **Focus** = live SoftLand + Arm.  
- **Settings** = all the knobs (currently a flat ingredient list — regroup later using §7).  
- **Runtime** = enforcer + msg_host + Edge extensions; Study `:8000` is optional for decide/track/kills after solo-pack Phase 1.
