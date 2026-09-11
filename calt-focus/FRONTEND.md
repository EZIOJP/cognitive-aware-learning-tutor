# CALT Focus — Frontend (FE)

WebView2 UI for Productivity. Built with `npm run build:focus` → `dist-focus/` (gitignored artifact; rebuild locally).

## Entry / config

| Path | Why |
|------|-----|
| `vite.focus.config.ts` | Design host `:5180`; serves `/calt-data` → `data/productivity/behavior`, `/calt-bible` → `data/productivity/bible` |
| `package.json` → `build:focus` / `dev:focus` | Focus Vite scripts |
| `src/utils/focusDesktopShell.ts` | Detects Focus shell vs Study browser |
| `src/utils/focusDataUrl.ts` | `calt-data.app` / `/calt-data` mirror base |
| `src/utils/bibleCorpus.ts` | Chapter text via Focus bible virtual host |
| `src/app/App.tsx` | Focus HashRouter; Study redirects `/bible` `/journal` home |
| `src/layout/AppSidebar.tsx` | Focus nav: Calendar, Plan, Settings, Focus, Bible, Journal |

## Pages / plugins

| Path | Why |
|------|-----|
| `src/pages/ProductivityPage.tsx` | Calendar / Plan / Settings hub (Focus-native plan steps) |
| `src/pages/FocusPage.tsx` | Focus Now |
| `src/pages/JournalPage.tsx` | Journal (Focus shell only) |
| `src/pages/bible/**` | Bible reader (Focus shell only) |
| `src/plugins/productivity_plugin.tsx` | Routes + Study interstitial |
| `src/plugins/bible_plugin.tsx` | Bible route; Study → home |

## Productivity UI (primary FE surface)

| Path | Why |
|------|-----|
| `src/components/productivity/**` | SoftLand, Arm, Settings hub, Plan cards, gates |
| `src/components/productivity/settings/ProductivitySettingsHub.tsx` | Settings sections |
| `src/components/productivity/EnforcerWriteGate.tsx` | Hard-block writes when pipe down |
| `src/components/productivity/OpenFocusInterstitial.tsx` | Study door closed |
| `src/components/productivity/ActivePlanBlockCards.tsx` | Active/next plan block |
| `src/components/productivity/FocusDesignHostBanner.tsx` | `:5180` banner |

## Clients (FE → Focus BE)

| Path | Why |
|------|-----|
| `src/lib/enforcerNativeCmd.ts` | WebView2 → `\\.\pipe\calt_enforcer_cmd` |
| `src/api/focusMirrors.ts` | Read `day_rollup` / status / softland mirrors |
| `src/api/plannerClient.ts` | Plan CRUD via pipe when Focus shell |
| `src/api/bibleClient.ts` | Bible gateway ops |
| `src/api/journalClient.ts` | Journal gateway ops |
| `src/api/behaviorClient.ts` | SoftLand/Arm helpers + Focus bridges |

## Out of FE review scope

Study vocab/math/notes/quiz pages, unrelated plugins, transcript studio.
