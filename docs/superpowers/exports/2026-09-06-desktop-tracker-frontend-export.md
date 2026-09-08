# CALT Desktop Tracker — Frontend Export (full)

**Date:** 2026-09-06  
**Pack:** [README](./2026-09-06-calt-desktop-tracker-README.md) · [Architecture](./2026-09-06-desktop-tracker-architecture-export.md)  
**Legal:** CALT original only.

---

## 1. Role of the frontend

React SPA is the **control + visibility** surface:

- **Focus** — gate status, PIN free, spend earned, enforcer health  
- **Calendar / Productivity** — planner + desktop usage bars (apps/sites)  
- **Sidebar IA** — Study / Focus / Life / System section bars  

Does **not** kill OS processes (native enforcer does).  
Does **not** SoftLand tabs (Gate extension does).

---

## 2. Routes

| URL | Component | Role |
|-----|-----------|------|
| `/productivity/focus` | `FocusPage` → `FocusControlPanel` | Control UI |
| `/productivity` | `ProductivityPage` | Calendar + desktop-stats |

Plugin: `src/plugins/productivity_plugin.tsx`  
Nav labels: **Focus**, **Calendar** (under Focus section).

---

## 3. Focus page layout

**File:** `src/components/productivity/FocusControlPanel.tsx`

| Section bar | Content |
|-------------|---------|
| **Now** | Mode, hard block, why/until, blocked list, incubation, earned balance |
| **Actions** | Free time (PIN), Spend earned |
| **Enforcer** | Owns kills?, last kill, install hint |
| **Related** | Links → Calendar, Study Loop, Bible, Lecture Notes |

APIs (`src/api/behaviorClient.ts`):

- `fetchFocusDashboard` → `GET /api/behavior/focus-dashboard`  
- `postFocusFreeOverride`  
- `postFocusSpendEarned`  

Poll ~8s. Snapshot includes `enforcer.last_kill` (maturity F3).

---

## 4. Productivity (usage UI)

**File:** `src/pages/ProductivityPage.tsx`

- `GET /api/behavior/desktop-stats`  
- Bars by **app**; browsers expand to **sites**  
- Shows `display_name` (e.g. Microsoft Edge)  
- Types: `AppSession`, `BrowserSite` in `behaviorClient.ts`

This is **usage** grouping (exe/site), separate from sidebar **feature** section bars.

---

## 5. Sidebar feature organization

| File | Role |
|------|------|
| `src/layout/navSections.ts` | Taxonomy Study / Focus / Life / System |
| `src/layout/AppSidebar.tsx` | Section headers + nav links |
| `src/plugins/types.ts` | `PluginNavItem.category` |
| Plugins | Each `navItems` tagged with `category` |

Collapsed rail: tooltip `Category · Feature`.

---

## 6. Browser extensions (FE-adjacent)

| Extension | Folder | Job |
|-----------|--------|-----|
| SelfTracker | `selftracker-extension/` | Active tab SESSION_END (`exe`, `url`, `domain`, `title`, `tab_id`) |
| CALT Gate | `calt-gate-extension/` | SoftLand / block via gate API |

Rebuild:

```bat
powershell -File scripts\build_extension_workers.ps1
```

Reload in `edge://extensions`.

---

## 7. Launchers

| Script | Opens |
|--------|--------|
| `run.bat` | Vite + API |
| `scripts/desktop_tracker/run_calt_desktop.bat` | Focus URL + native console |
| `run_calt_desktop_qt.bat` | Legacy Qt (optional) |

Default Focus: `http://127.0.0.1:5173/productivity/focus`

---

## 8. Frontend file list

```
src/pages/FocusPage.tsx
src/pages/ProductivityPage.tsx
src/components/productivity/FocusControlPanel.tsx
src/api/behaviorClient.ts
src/layout/AppSidebar.tsx
src/layout/navSections.ts
src/layout/AppTopBar.tsx
src/plugins/productivity_plugin.tsx
src/plugins/types.ts
selftracker-extension/background.js
calt-gate-extension/background.js
```

---

## 9. Cross-links

- Architecture: [architecture-export](./2026-09-06-desktop-tracker-architecture-export.md)  
- Backend: [backend-export](./2026-09-06-desktop-tracker-backend-export.md)  
- Native: [native-export](./2026-09-06-desktop-tracker-native-export.md)
