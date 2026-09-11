# Focus frontend (FE)

UI for CALT Focus (Calendar / Plan / Settings / Focus / Bible / Journal).

**Product context:** see [../README.md](../README.md) (idea + architecture).  
This folder is only the **Vite entry**; most React still lives in shared repo `src/` so Study can show interstitials.

## This folder

| Item | Path |
|------|------|
| Vite config | `calt-focus/frontend/vite.config.ts` |
| Scripts | `npm run dev:focus` · `npm run build:focus` → repo `dist-focus/` |
| Design host | http://127.0.0.1:5180/ |
| Mirrors | `/calt-data` → `data/productivity/behavior` · `/calt-bible` → `data/productivity/bible` |

Writes (SoftLand/Arm/Plan) need **`calt_focus.exe`** + enforcer pipe — the design host is read/hot-reload only.

## Shared React sources to review (repo `src/`)

- Pages: `ProductivityPage.tsx`, `FocusPage.tsx`, `JournalPage.tsx`, `pages/bible/**`
- UI: `components/productivity/**` (Settings hub, SoftLand, Arm, plan cards, write gate)
- Clients: `api/focusMirrors.ts`, `plannerClient.ts`, `bibleClient.ts`, `journalClient.ts`, `behaviorClient.ts`
- Bridge: `lib/enforcerNativeCmd.ts` → named pipe
- Shell detect: `utils/focusDesktopShell.ts`, `focusDataUrl.ts`, `bibleCorpus.ts`
- Plugins: `productivity_plugin.tsx`, `bible_plugin.tsx`
- Chrome: `layout/AppSidebar.tsx`, `app/App.tsx` (Focus = HashRouter)

Out of scope: vocab, math, notes, quiz Study pages.
