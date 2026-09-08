# CALT Desktop Tracker v2 — decisions + architecture

**Date:** 2026-09-06  
**Status:** Decisions locked in plan — see [2026-09-06-calt-desktop-tracker-v2.md](../plans/2026-09-06-calt-desktop-tracker-v2.md) (§0 questions still open)  
**Goal:** Cold Turkey–*like* installable desktop blocker/control app for CALT: clearer status, reliable enforcement, incubation + earned free time on the **existing** gate brain.  
**Not:** Copying Cold Turkey binaries, DBs, or proprietary code. Patterns only.

---

## 0. How to use this page

1. Answer every **Decision** below (A/B/C or short note).  
2. Skim **Recommended defaults** — reply “defaults OK” if you agree.  
3. Approve or edit **Architecture**.  
4. Then we write the implementation plan and build in phases.

---

## 1. Product intent (locked from chat)

| Intent | Owner said |
|--------|------------|
| Feel | Cold Turkey–like Dashboard: what’s blocked, why, until when, how to get more time |
| Reliability | Prefer Windows-service-class enforcement over “just a Python window” |
| Backend | Keep FastAPI / SQLite / study stack in Python |
| Policy | Prefer **presenting** existing gate rules clearly first; don’t invent a second block engine unless we choose to |
| Shipping | Installable Windows application (Start Menu / autostart), not only `run_calt_desktop.bat` |

---

## 2. All open decisions (answer these)

### D1 — Scope of v2 (pick one)

- [ ] **S1** Dashboard readability + packaging only (fastest; enforcement stays as today)  
- [ ] **S2** S1 + **Windows service enforcer** for hard-block kills / keep-alive (**recommended**)  
- [ ] **S3** S2 + richer “named blocks + breaks” config layer (CT-like break types on top of gate)  
- [ ] **S4** Full CT-class rewrite (native hosts + new block DB) — **not recommended**

**Your answer:** ___

### D2 — UI shell

- [ ] **U1** Keep PySide6 tabs; add a plain-language **“Right now”** panel (Qt only)  
- [ ] **U2** PySide6 shell + **WebView2 Dashboard** (HTML like CT) for status; Rules/Device stay Qt or also HTML later (**recommended**)  
- [ ] **U3** Full WebView2 app (almost all UI in HTML)

**Your answer:** ___

### D3 — “Ask for more time” (presentation vs new rules)

- [ ] **T1** Only surface **existing** Free time (PIN) + remaining minutes + links (**recommended for v2a**)  
- [ ] **T2** T1 + nicer break dialog (duration presets) still using `set_free_override`  
- [ ] **T3** New break types (allowance / reward / sessions) — bigger lane

**Your answer:** ___

### D4 — Windows service

- [ ] **V0** No service in v2 (UI + installer only)  
- [ ] **V1** Thin service: boot start, hard-block process kills, restart if crashed; policy still from Python modules/DB (**recommended** with S2)  
- [ ] **V2** Service also owns browser SoftLand (would fight extension — avoid)

**Your answer:** ___

### D5 — Installer / packaging

- [ ] **P1** Improved `run_calt_desktop.bat` + Start Menu shortcut script only  
- [ ] **P2** Proper installer (Inno Setup / similar): Start Menu, optional autostart, uninstall (**recommended**)  
- [ ] **P3** MSIX / Store-style package

**Your answer:** ___

### D6 — Relationship to website `/productivity`

- [ ] **W1** Unchanged (calendar on web; banner “managed in Desktop”) (**recommended**)  
- [ ] **W2** Hide more gate UI on web; deep-link “Open CALT Desktop”  
- [ ] **W3** Embed calendar in Desktop (out of scope for early v2)

**Your answer:** ___

### D7 — Morning gate / Bible / Plan

- [ ] **M1** Keep current morning flow; Dashboard only *explains* it (**recommended**)  
- [ ] **M2** Move morning confirm fully into Desktop v2 UI polish  
- [ ] **M3** Change morning rules (new product policy — say what)

**Your answer:** ___

### D8 — Extension

- [ ] **E1** Keep polling FastAPI `:8000` (**recommended** short term)  
- [ ] **E2** Prefer hub `:8765` when API down  
- [ ] **E3** Bundle extension install into Desktop installer

**Your answer:** ___

### D9 — Name / branding

- [ ] Keep **CALT Desktop**  
- [ ] Rename to **CALT Blocker** / **CALT Focus** / other: ___

**Your answer:** ___

### D10 — Timeline priority

- [ ] Ship readable Dashboard ASAP, service next  
- [ ] Service + Dashboard together before you use daily  
- [ ] Installer first, then UI

**Your answer:** ___

---

## 3. Recommended defaults (if you say “defaults OK”)

| Decision | Default |
|----------|---------|
| D1 Scope | **S2** |
| D2 UI | **U2** (WebView2 Dashboard + Qt shell) |
| D3 More time | **T2** (PIN free-time with clearer dialog) |
| D4 Service | **V1** |
| D5 Installer | **P2** |
| D6 Web | **W1** then light **W2** |
| D7 Morning | **M1** |
| D8 Extension | **E1**, later **E3** |
| D9 Name | **CALT Desktop** (subtitle: Focus / Blocker) |
| D10 Order | Dashboard → Service → Installer polish |

---

## 4. Architecture (proposed)

### 4.1 Principles

1. **One policy brain** — keep `browser_gate_policy` + `distraction_gate` + productivity policy SQLite/JSON.  
2. **Two surfaces** — Dashboard (status) vs Editors (Rules / Schedules / Device).  
3. **Three processes (v2)** — (a) UI app, (b) optional **enforcer service**, (c) FastAPI when study stack needed.  
4. **No second SRS / no study rewrite.**  
5. **No Cold Turkey code** — inspiration only.

### 4.2 Diagram

```text
┌─────────────────────────────────────────────────────────┐
│  CALT Desktop v2 (installed app)                        │
│  ┌──────────────────┐  ┌─────────────────────────────┐  │
│  │ WebView2         │  │ Qt tabs (existing)          │  │
│  │ Dashboard        │  │ Rules · Schedules · Device  │  │
│  │ Active / Upcoming│  │ Bible · Plan · Watch · Voice│  │
│  │ Until / Free time│  │                             │  │
│  └────────┬─────────┘  └──────────────┬──────────────┘  │
│           │ local HTTP or QWebChannel │                 │
│           └────────────┬──────────────┘                 │
│                        ▼                                │
│              Desktop bridge (Python)                    │
│              latest_gate / policy / free override       │
└────────────────────────┬────────────────────────────────┘
                         │ same DB / modules
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
   Enforcer service   FastAPI:8000    Extension
   (hard-block kills)  (study+gate    SoftLand/DNR
   boot / restart      API + WS)
```

### 4.3 Components

| Unit | Responsibility | Depends on |
|------|----------------|------------|
| **Dashboard HTML** | Naive status: active blocks, why, until when, CTAs | Bridge JSON only |
| **Bridge** | `compute_distraction_gate` / policy / `set_free_override` | Existing behavior modules |
| **Qt editors** | Same Rules/Device/Schedules as today (copy polish) | Existing tabs |
| **Enforcer service** | Poll gate or watch invalidation; `should_hard_block` kills; stay alive | Policy files/DB; no UI |
| **Installer** | Install files, Start Menu, optional Task Scheduler/autostart, uninstall | Built artifacts |
| **FastAPI** | Unchanged study + gate HTTP for extension | Existing |

### 4.4 Dashboard content (naive user format)

Inspired by Cold Turkey’s **Active / Upcoming / Summary**, fed only by current gate:

1. **Right now** — Games/apps armed? Browser mode name? Morning next?  
2. **Why** — one sentence (Bible, plan, study goal, schedule window, free override).  
3. **Until when** — free-time remaining **or** next schedule change.  
4. **What’s blocked** — short bullets from policy (exe count, categories, device toggles).  
5. **What you can do** — Free time (PIN) · Open Rules · Open Schedules · Open Device · Disarm (existing UNLOCK).

### 4.5 Phased delivery

| Phase | Deliverable | Done when |
|-------|-------------|-----------|
| **v2a** | Dashboard (WebView2 or Qt) + plain-language status + Free time CTA | Owner can answer “what’s blocked / until when” without reading logs |
| **v2b** | Windows service enforcer + autostart | Tracker kill survives closing the UI window |
| **v2c** | Inno (or similar) installer | Double-click install → Start Menu → runs |
| **v2d** (optional) | Named-block / break config layer | Only if T3 / S3 chosen |

### 4.6 Non-goals (v2)

- Replacing Chrome/Edge SoftLand with a desktop SoftLand  
- Cloning Cold Turkey allowance/reward/session engines (unless D3=T3)  
- Moving GRE/quiz/notes into the blocker app  
- Embedding full web Productivity calendar in v2a–c  
- Android Device Gate

### 4.7 Risks

| Risk | Mitigation |
|------|------------|
| WebView2 missing on machine | Installer bundles Evergreen bootstrapper or fallback Qt dashboard |
| Service + UI race | Service owns kills; UI owns settings; single policy files |
| Scope creep to “CT clone” | Phases v2a→c; S4 explicitly rejected unless reopened |
| Legal | No CT code; original UI/strings |

### 4.8 Success criteria

- [ ] Dashboard shows active / why / until in plain English  
- [ ] Free time remaining visible when override active  
- [ ] One-click path to Rules / Schedules / Device / Free time  
- [ ] (If S2) Closing UI does not stop hard-block enforcement  
- [ ] (If P2) Installed app launches without opening a terminal  
- [ ] Study stack (`run.bat` / `:8000`) still works  
- [ ] Extension still receives gate payload  

---

## 5. What we need from you

Reply with either:

1. **`defaults OK`** — we treat §3 as approved and proceed to implementation plan for **v2a → v2b → v2c**, or  
2. **Answers** to D1–D10 (even partial), then we lock the architecture and plan.

After answers: implementation plan under `docs/superpowers/plans/2026-09-06-calt-desktop-tracker-v2.md`, then build.
