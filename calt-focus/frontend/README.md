# Focus frontend (FE)

Vite entry for CALT Focus UI.

| Item | Path |
|------|------|
| Vite config | `calt-focus/frontend/vite.config.ts` |
| npm scripts | `npm run dev:focus` · `npm run build:focus` → repo `dist-focus/` |
| Design host | http://127.0.0.1:5180/ |
| Mirrors | `/calt-data` → `data/productivity/behavior` · `/calt-bible` → `data/productivity/bible` |

## Shared React sources (repo `src/`)

Focus and Study still share the React tree. **Review these for Focus FE:**

- `src/pages/ProductivityPage.tsx`, `FocusPage.tsx`, `JournalPage.tsx`, `src/pages/bible/**`
- `src/components/productivity/**`
- `src/api/{focusMirrors,plannerClient,bibleClient,journalClient,behaviorClient}.ts`
- `src/lib/enforcerNativeCmd.ts`
- `src/utils/{focusDesktopShell,focusDataUrl,bibleCorpus}.ts`
- `src/plugins/{productivity_plugin,bible_plugin}.tsx`
- `src/layout/AppSidebar.tsx` (Focus nav)
- `src/app/App.tsx` (Focus HashRouter)

Study-only pages (vocab, math, notes, quiz) are out of scope.
