# Focus frontend (FE)

Lean **Focus-only** SPA for `calt_focus.exe` (Calendar / Plan / Settings / Focus / Bible / Journal).

**Product context:** [../README.md](../README.md)  
**Design:** [docs/superpowers/specs/2026-09-14-lean-focus-fe-design.md](../../docs/superpowers/specs/2026-09-14-lean-focus-fe-design.md)

## This folder

| Item | Path |
|------|------|
| Vite config | `calt-focus/frontend/vite.config.ts` |
| Entry | `index.html` → `app/main.tsx` → `app/FocusApp.tsx` |
| Scripts | `npm run dev:focus` · `npm run build:focus` → repo `dist-focus/` |
| Design host | http://127.0.0.1:5180/ |

**Does not load** Study plugins (GRE / math / notes / mermaid / EEG registry). Shared productivity React still lives under repo `src/` and is imported selectively.

Writes (SoftLand/Arm/Plan) need **`calt_focus.exe`** + enforcer pipe.

## Shared sources (library)

- Pages: `ProductivityPage`, `FocusPage`, `JournalPage`, `pages/bible/**`
- UI: `components/productivity/**`
- Clients: `plannerClient`, `focusMirrors`, `bibleClient`, `journalClient`, `enforcerNativeCmd`
- Chrome: `layout/AppSidebar` (Focus shell sections)

Study full app entry remains `src/main.tsx` + `src/app/App.tsx` for `:8000`.
