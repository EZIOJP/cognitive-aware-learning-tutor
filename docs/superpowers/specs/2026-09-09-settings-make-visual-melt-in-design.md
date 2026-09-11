# Settings Make UI — visual melt-in (theme tokens)

**Date:** 2026-09-09  
**Status:** Implemented (Approach 1) — theme tokens + gloss; plan done  
**Approach:** **1** — Restyle `MakeSettingsApp` + wrapper with app theme tokens + `gloss-panel`  
**Not chosen:** 2 (CSS hex bridge) · 3 (full shadcn rebuild this pass)

**Related**

| Doc | Role |
|-----|------|
| [Settings intuitive UX handoff](../exports/2026-09-09-settings-intuitive-ux-handoff.md) | IA + SoftLand ≠ Arm teaching (unchanged) |
| [BLOCKING_RULES.md](../../BLOCKING_RULES.md) | Rule copy SoT |
| [Settings UI overhaul](2026-09-08-productivity-settings-ui-overhaul-design.md) | Prior hub groups (superseded IA by Make 5-nav) |

---

## 1. Goal

Make the imported Make Settings shell **look like** Calendar / Plan / the rest of CALT:

- Light **and** dark via theme tokens (`background`, `foreground`, `card`, `border`, `primary`, `muted-foreground`, `accent`, semantic emerald/rose/amber).
- Same **card / radius / gloss** language as Productivity page (`gloss-panel`, `rounded-3xl` outer, `rounded-xl` cards, `rounded-lg` controls).
- **Logic and IA unchanged** — same sections, same SoftLand ≠ Arm teaching, same demo state handlers.

Success: toggle app light/dark and Settings still matches Calendar/Plan; no “foreign dark Inter mock” chrome.

---

## 2. Non-goals

- Wire live enforcer gateway / SoftLand status (demo state stays).
- Drop or merge the left Settings nav (Overview · Rules · Unlock · Productive · Tools).
- Rebuild on shared shadcn `Card`/`Button` (Approach 3) — optional later.
- Change SoftLand / Arm / unlock product rules.
- Figma re-export.

---

## 3. Files to touch

| File | Change |
|------|--------|
| `src/components/productivity/ProductivitySettingsTab.tsx` | Wrapper: drop hardcoded `#0f0f0f` / `border-white/[0.06]`; use `gloss-panel rounded-3xl border border-border/50 bg-background` (or equivalent). |
| `src/components/productivity/settings/make/MakeSettingsApp.tsx` | Replace hardcoded hex + forced Inter with theme + gloss classes on shell, primitives (`Card`, `Badge`, `Toggle`, `SectionHeader`, `SettingRow`), and section surfaces. Keep structure and state. |

No new packages. No C++ / tray changes.

---

## 4. Visual mapping (Make → app)

| Make (today) | App (target) |
|--------------|--------------|
| `bg-[#0f0f0f]` / `#0d0d0d` / `#191919` | `bg-background` / `bg-card` / `bg-muted` / `bg-background/50` |
| `border-[#191919]` / `#222` | `border-border/50` |
| `text-[#ccc]` / `#555` / `#444` | `text-foreground` / `text-muted-foreground` |
| Forced `Inter` | Inherit app font stack |
| Custom `Card` `bg-[#191919] rounded-lg` | `gloss-panel rounded-xl border border-border/50` |
| Primary blue hex buttons | `bg-primary text-primary-foreground` |
| Secondary muted buttons | `border border-border/50 bg-background/50 hover:bg-accent/60` |
| SoftLand green / Arm red / Study amber | Emerald / rose / amber semantic classes (theme-safe opacity) |
| Outer Settings mount `rounded-2xl` dark box | `gloss-panel rounded-3xl` matching Productivity header |

**Keep:** 5-nav IA, SL/ARM sidebar pills, SoftLand vs Arm Overview teaching cards, Plan—Now strip, earn / Arm controls, Rules / Unlock / Productive / Tools content structure.

---

## 5. Verification

1. `npm run build:focus` (or Vite Settings under Study) — no TS errors.
2. Open Productivity → Settings in **dark** and **light** theme — shell, cards, nav, and Overview readable; no leftover hard dark panels that ignore theme.
3. SoftLand ON ≠ Arm copy and controls still behave as before (demo toggles).
4. Tray **Update UI** or rebuild + reload Focus so `dist-focus` picks up the restyle.

---

## 6. Spec self-review

- No placeholders / TBD left in scope.
- No contradiction with product lock (SoftLand sites vs Arm kills).
- Scope is visual melt-in only; live data and Approach 3 explicitly out.
- Ambiguity resolved: Approach **1** only this pass.
