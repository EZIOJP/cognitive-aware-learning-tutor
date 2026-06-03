# Stitch automation (API)

Use when Cursor MCP shows **stitch** connected, or run these scripts directly.

## Prerequisites

- Node.js 18+
- API key in **Cursor → Settings → MCP** (`~/.cursor/mcp.json` → `mcpServers.stitch.headers.X-Goog-Api-Key`)

## Commands

```bat
scripts\stitch\run.bat verify
scripts\stitch\run.bat life-clock
scripts\stitch\run.bat study-hub
scripts\stitch\run.bat all
```

Or:

```powershell
cd "Cognitive-Aware Learning Tutor"
npm install
node scripts/stitch/verify.mjs
node scripts/stitch/generate.mjs life-clock
```

## Download Stitch screens (HTML + screenshots)

```bat
npm run stitch:download
```

Exports **Cognitive-Aware Learning Hub** to:

`docs/stitch-export/cognitive-aware-learning-hub/`

Each folder: `screen.html`, `screenshot.jpg`, `metadata.json`. Index: `index.json`.

## Output (generation)

- `docs/stitch-output/manifest-*.json` — project id, screen ids, timestamps (no secrets)

## Cursor MCP (you already added this)

Reload MCP after editing `~/.cursor/mcp.json`, then in a **new Agent chat**:

```text
@docs/STITCH_LIFE_CLOCK_PROMPT.txt
Use Stitch MCP: list_projects, then generate_screen_from_text for the Life Clock widget (DESKTOP).
```

## Security

- Never commit API keys
- `.env.stitch.local` is gitignored (optional override)
