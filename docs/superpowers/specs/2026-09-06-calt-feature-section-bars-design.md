# CALT feature organization — section bars (sidebar + Focus)

**Date:** 2026-09-06  
**Status:** Approved — implemented 2026-09-06  
**Decision:** Approach **1** — category section bars with feature links as sub-items (not nested routes, not usage-app bars).

---

## Goal

Organize **app features** so the UI reads as:

```text
Category (section bar)
  └─ Feature (sub-item / link / control)
```

Apply in **both**:

1. Left **sidebar** (`AppSidebar`)
2. **Focus** page (`FocusControlPanel` / Focus page)

Do **not** regroup Productivity time bars by website/app for this work.

---

## Categories (locked draft)

| Section bar | Sub-features |
|-------------|--------------|
| **Study** | Lecture Notes, Review, Journal, GRE Vocab, Math Tutor, Study Room |
| **Focus** | Focus (this page), Calendar / Productivity, (optional deep-links: Gate / enforcer status stay on Focus) |
| **Life** | Bible, Life Tracker, Nutrition |
| **System** | Home, Settings, Admin (admin if role) |

Plugins keep registering their own `navItems`; sidebar **groups** them by a shared `navCategory` (or path map fallback) instead of inventing a second nav source.

---

## Sidebar behavior

- When **expanded**: show category label (muted, uppercase / small), then NavLinks indented under it.
- When **collapsed** (icon rail): show icons only; **tooltip** = `Category · Feature` (e.g. `Focus · Calendar`). No category headers in icon mode (too tall).
- Order within a category follows existing `NAV_ORDER` preference.
- Disabled / inactive plugins stay omitted (same as today).

### Implementation sketch

- Extend `PluginNavItem` with optional `category?: "study" | "focus" | "life" | "system"`.
- Fallback map by path prefix for items missing `category`.
- `AppSidebar` renders `Record<category, items[]>` with section headers.

---

## Focus page behavior

Same taxonomy as visual scaffolding:

| Section | Content |
|---------|---------|
| **Now** (or under Focus) | Gate mode, lock, incubation, earned balance — live snapshot |
| **Actions** | PIN free time, spend earned |
| **Enforcer** | Native owns kills, last kill, link to install docs / Productivity |
| **Related** | Links: Calendar (`/productivity`), optional Study / Bible shortcuts |

Keep existing API calls; **layout only** (section headers + grouped cards). No new backend.

---

## Out of scope

- Nested URL routes (`/focus/...`)
- Collapsible category trees
- Changing desktop-stats aggregation (Edge / sites)
- PySide6 Qt redesign

---

## Acceptance

- [ ] Expanded sidebar shows 4 section bars with features underneath
- [ ] Collapsed sidebar still works (icons + tooltips)
- [ ] Focus page sections match Focus / Actions / Enforcer / Related
- [ ] Existing routes and plugins still navigate correctly
- [ ] No change to time-tracking bar grouping by app/site

---

## Owner

Approve this file (or edit category names / membership), then implementation plan → code.
