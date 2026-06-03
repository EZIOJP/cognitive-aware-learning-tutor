# Life clock themes (Stitch)

Project: **Cognitive-Aware Learning Hub** (`7612682550096205798`)  
Export root: `docs/stitch-export/cognitive-aware-learning-hub/` (HTML + `screenshot.jpg` per screen, gitignored)

| Screen | Folder | Screen ID |
|--------|--------|-----------|
| 24-hour Life Clock (day / infographic spec) | `09-life-clock-infographic-spec/` | `6ec2a1ec0a7d497ab4320ea13a8d173d` |
| Oceanic Aurora variant | `10-life-clock-oceanic-aurora/` | `d22db5e27072452d88b70300c785f28d` |
| **Midnight Amber variant** | `11-life-clock-midnight-amber/` | `fca1724f9b9a45d2b9b38a51a1b49650` |

Re-download all screens (uses hosted URLs + `curl -L`):

```bat
npm run stitch:download
```

# Midnight Amber (implemented in app)

Source screen: **Life Clock - Midnight Amber Variant**

## Enable in app

1. **Settings → Theme → Accent → Midnight Amber** (dark mode recommended)
2. Or first visit in dark mode uses Midnight Amber by default

## Tokens (implemented in `src/styles/midnight-amber.css`)

| Role | Hex |
|------|-----|
| Background | `#121212` |
| Primary (amber) | `#f59e0b` |
| Secondary (gold) | `#fbbf24` |
| Sleep segment | `#f59e0b` |
| Study segment | `#fbbf24` |
| Math segment | `#d97706` |

## Life clock UI

`LifeClockWidget` uses Stitch stroke-ring layout when accent is `midnight-amber` or `amber` in dark mode:

- Dashed track + segment strokes
- Glass metric cards
- Amber gradient day-progress bar
- Legend table with HH:MM times

Re-download screen:

```bat
npm run stitch:download
```
