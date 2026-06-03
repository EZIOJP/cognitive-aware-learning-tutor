# Stitch MCP — Cursor setup (done by you) + what to run next

You added Stitch in **Cursor → Settings → MCP**. Finish with these steps.

## 1. Reload MCP in Cursor

1. Open **Settings → MCP**
2. Find **stitch** — toggle **Off**, then **On**, or click **Refresh**
3. Status should be green / **Connected**
4. You should see tools like `list_projects`, `generate_screen_from_text`, `create_project`

If it stays red:

- Confirm `X-Goog-Api-Key` in `C:\Users\Lenovo\.cursor\mcp.json` is your real key (not a placeholder)
- Restart Cursor
- Fallback: use the **npx proxy** in [Google Stitch MCP guides](https://stitch.withgoogle.com) or run `scripts\stitch\run.bat verify` instead

## 2. Verify API (no MCP required)

```bat
scripts\stitch\run.bat verify
```

Expected: `OK: Stitch API connected` and a project count.

## 3. Generate Life Clock (automated)

```bat
scripts\stitch\run.bat life-clock
```

Uses `docs/STITCH_LIFE_CLOCK_PROMPT.txt`. Takes a few minutes. Result manifest:

`docs/stitch-output/manifest-*.json`

Open [stitch.withgoogle.com](https://stitch.withgoogle.com) to view and export screens.

## 4. Generate full Study Hub (optional)

```bat
scripts\stitch\run.bat study-hub
```

Uses `docs/STITCH_PROMPT.txt` (6 screens).

## 5. Use Stitch inside Cursor Agent (after MCP is green)

Start a **new chat** (so tools load) and paste:

```text
@docs/STITCH_LIFE_CLOCK_PROMPT.txt

Use Stitch MCP tools only:
1. list_projects — use "Cognitive-Aware Learning Tutor" or create_project with that title
2. generate_screen_from_text — DESKTOP, prompt = full Life Clock brief (data infographic, no color palette)
3. Tell me the Stitch project URL and screen names when done
```

For all screens:

```text
@docs/STITCH_PROMPT.txt @docs/STITCH_DESIGN_SPEC.md

Use Stitch MCP: create or open project "Cognitive-Aware Learning Tutor", then generate DESKTOP screens per STITCH_PROMPT.txt. One generation per screen if needed.
```

## 6. After designs are approved

Frontend implementation stays deferred until you sign off mocks in Stitch. Then implement from `STITCH_DESIGN_SPEC.md` + exported assets.

## Security

- API key lives only in `~/.cursor/mcp.json` or `.env.stitch.local` (gitignored)
- Rotate the key if it was ever pasted in chat or committed

## Repo files

| File | Purpose |
|------|---------|
| `scripts/stitch/generate.mjs` | API generation |
| `scripts/stitch/verify.mjs` | Connection test |
| `docs/STITCH_LIFE_CLOCK_PROMPT.txt` | Life Clock brief |
| `docs/STITCH_PROMPT.txt` | Full app brief |
| `docs/STITCH_DESIGN_SPEC.md` | Full spec reference |
