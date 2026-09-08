# CALT Focus shell handover — blocker + calendar/plan

**Date:** 2026-09-07  
**Status:** Approved — implementing (blocker + calendar/plan in shell; study in browser)  
**Default open:** Calendar  
**Related:** [2026-09-07-calt-blocker-study-split-decisions.md](./2026-09-07-calt-blocker-study-split-decisions.md)

## Owner intent

Hand the **blocker + calendar/plan** experience to **`calt_focus.exe`** (tray + WebView2).  
**Study product** (notes, Study Loop, GRE, Math, Journal, Bible reader UI, etc.) stays the **normal webapp** in the browser.

No Qt. No second SoftLand UI in C++. React inside WebView2 remains the UI.

## Product split

| In `calt_focus` (desktop app) | In browser webapp |
|-------------------------------|-------------------|
| Focus / Enforcer (Arm, kill list, lock) | Notes / Lecture Notes |
| SoftLand settings (`#policy`) | Study Loop / Review Hub |
| Productivity **Calendar** | GRE / Math / Journal |
| Productivity **Plan** | Bible reader (study) |
| Productivity **Settings** hub (blocker-facing) | Wearables deep config if needed |
| Tray: Run stack, Open Focus, Open Settings, Open Calendar/Plan | Full site chrome / study nav |

Shared: same React routes, same `:8000` API, same SQLite. Different **door**.

## Architecture

```text
calt_focus.exe
  tray + WebView2
       → default: #/productivity?tab=settings  (or calendar)
       → Focus / Plan / Calendar / Settings only
       → desktop shell mode: hide study sidebar / study-only nav

Browser
       → full AppShell + study plugins
       → can still open /productivity if needed (not primary)

calt_enforcer.exe     → kills (unchanged)
Python :8000          → SoftLand compute + study + planner APIs
```

## Desktop shell mode (React)

Detect Focus shell host (existing: `calt.app`, `127.0.0.1:5174`, hash router / user agent or `?shell=focus`):

- Show **Productivity** nav only (Calendar / Plan / Settings / Focus deep link).
- Hide GRE, Study Loop, Notes, etc. from sidebar (links can still “Open in browser” if useful).
- Optional top bar: “Study site →” opens system browser to `http://127.0.0.1:5173/` or configured origin.

## Tray menu (target)

| Item | Navigates |
|------|-----------|
| Run (enforcer + API; prebuilt UI) | existing |
| Open Focus | `#/productivity/focus` |
| Open Settings | `#/productivity?tab=settings` |
| Open Calendar | `#/productivity` or `?tab=calendar` |
| Open Plan | `#/productivity?tab=plan` |
| Quit | existing |

## Out of scope

- Porting SoftLand/Arm UI to C++ widgets  
- Qt / Electron  
- Moving notes / Study Loop into the shell  
- P5 native SoftLand  

## Success

1. Daily blocker + day calendar/plan happen in `calt_focus` without opening Chrome for that.  
2. Study work still happens in the webapp.  
3. One React codebase; shell only frames + filters nav.  

## Implementation order (after approve)

1. `shell=focus` (or host detect) → Productivity-only nav  
2. Tray: Calendar + Plan entries (Settings/Focus already)  
3. Default open URL = Settings or Calendar (owner pick)  
4. Optional “Open study site” balloon/menu item  

---

**Approve** this split (and default open: **Settings** vs **Calendar**) to implement.
