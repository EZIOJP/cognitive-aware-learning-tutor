# Hero theme layers

Composable opt-in styling from Google Stitch exports (Lemillion / Spiderman hero toolkit). Defaults preserve the calm study app.

## Layer model

| Layer | Attribute | Default | Options |
|-------|-----------|---------|---------|
| Color preset | `data-accent-preset` | `lemillion-heroic-spotlight` | All presets in Settings |
| Typography | `data-typography-pack` | `study` | `study`, `hero`, `motivator` |
| Surface | `data-surface-style` | `gloss` | `gloss`, `comic`, `flat` |
| Button variant | `data-button-variant` | `default` | `default`, `comic`, `chamfer`, `dashed`, `skew`, `shiny` |
| App button style | `data-button-style` | `default` | From `BUTTON_STYLES` |
| Background | `data-bg-style` | `minimal` | From `BACKGROUND_STYLES` |
| Motion | `data-motion-level` | `off` | `off`, `subtle`, `hero` |

Preset bundles live in `src/theme/layers.ts` (`PRESET_LAYER_BUNDLES`). Applying a preset sets colors **and** suggested layers; you can override any layer afterward.

## Token priority (dark / light mode)

Semantic colors follow a fixed pipeline — see also `.cursor/rules/theme-contrast.mdc`:

| Priority | Source | Role |
|----------|--------|------|
| 1 | `LIGHT_BASE` / `DARK_BASE` | Scheme base palette |
| 2 | `resolvePresetTokens()` | Preset colors for **active** scheme only |
| 3 | `ensureSemanticPairs()` | Auto-fix missing `primaryForeground`, `cardForeground`, etc. |
| 4 | Layer `data-*` attrs | Comic/gloss/motion (no raw text colors) |
| 5 | Decorative CSS | Gradients, clock vars — never duplicate semantic tokens |

**Invariant:** `data-color-scheme`, `.dark`, and token derivation must always match. Dark-only presets use `deriveLightTokensFromDark()` when the user toggles light mode.

## Safety rules

- **Study defaults**: `resetStudyDefaults()` in Theme Settings restores preset `default`, gloss surfaces, study typography, no motion, no hero widgets.
- **Gated CSS**: Hero styles are in `src/styles/hero-toolkit.css` and only apply when `html[data-*]` attributes are non-default.
- **Reduced motion**: Shine/float/permeate animations are disabled when `prefers-reduced-motion: reduce`.
- **shadcn buttons**: `Button` adds `hero-styled` classes only when `buttonVariant !== "default"`.

## Files

- `src/theme/layers.ts` — types, bundles, option lists
- `src/theme/applyLayers.ts` — DOM attribute apply/clear
- `src/context/ThemeContext.tsx` — state, persistence, `applyPreset`, `resetStudyDefaults`
- `src/components/hero/` — preview primitives (`HeroButton`, `HeroPanel`, `HeroProgress`, `LemillionAssistant`)
- `src/pages/settings/ThemeSettingsPage.tsx` — accordion UI + toolkit preview
- `src/layout/AppSidebar.tsx`, `AppTopBar.tsx` — typography hooks
- `src/pages/HomePage.tsx` — optional dashboard widgets

## Dashboard widgets

Enable in **Settings → Theme → Dashboard widgets**:

- **Lemillion assistant** — motivational bubble (uses AI summary when available)
- **Hero progress** — bar from daily performance tier

## Stitch source assets

Exported HTML/JPG under `docs/stitch-export/` and previews in `public/theme-previews/`.
