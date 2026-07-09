# 9Router — unlimited AI routing for Cursor + CALT

[9Router](https://github.com/decolua/9router) v0.5.20+ is a local AI gateway between your coding tools and 40+ providers. RTK token compression saves 20–40% on every request; 3-tier fallback (subscription → cheap → free) keeps sessions running when quotas hit. CALT can route notes/quiz through it too.

**Do not rebuild this inside CALT** — install upstream and point clients at `http://localhost:20128/v1`.

## Quick start (Windows)

```bat
scripts\9router\install_9router.bat
scripts\9router\start_9router.bat
```

Dashboard: [http://localhost:20128/dashboard](http://localhost:20128/dashboard)

First login: set `INITIAL_PASSWORD` in 9Router's `.env`, or use fallback `123456` on first visit.

## Step 1 — Connect providers

Dashboard → **Providers**:

### Free (recommended for $0 coding)

| Provider | Prefix | What you get |
|----------|--------|----------------|
| **Kiro AI** | `kr/` | Claude 4.5 + GLM-5 + MiniMax — unlimited free |
| **OpenCode Free** | `oc/` | No auth, auto-fetch models — unlimited free |
| **Vertex AI** | — | $300 GCP credits (Gemini 3 Pro, DeepSeek, GLM-5) |

> **Note (2026):** iFlow, Qwen Code, and Gemini CLI free tiers were discontinued. Use Kiro / OpenCode Free / Vertex instead.

### Subscription (if you already pay)

| Provider | Prefix |
|----------|--------|
| Claude Code | `cc/` |
| Codex | `cx/` |
| GitHub Copilot | — |
| Cursor | OAuth in dashboard |

### Cheap backup

| Provider | Cost |
|----------|------|
| GLM-5.1 | ~$0.6/1M tokens |
| MiniMax M2.7 | ~$0.2/1M tokens |

## Step 2 — Create a combo (recommended)

Dashboard → **Combos** → create e.g. `free-forever`:

```text
1. kr/claude-sonnet-4.5    (Claude 4.5 free)
2. kr/glm-5                (GLM-5 free via Kiro)
3. oc/<auto>               (OpenCode Free fallback)
```

Or `maximize-claude` if you have Claude Pro:

```text
1. cc/claude-opus-4-7
2. glm/glm-5.1
3. kr/claude-sonnet-4.5
```

Combos are the main way 9Router does automatic fallback — use the combo name as your model.

## Step 3 — Copy API key

Dashboard → **Settings** → copy API key. Use as `Bearer` token in Cursor and CALT.

Enable **RTK** in Dashboard → Endpoint settings (on by default, saves 20–40% tokens).

## Step 4 — Point Cursor at 9Router

### Automated helper scripts (Windows)

```bat
scripts\9router\start_9router.bat
scripts\9router\setup_cursor_9router.bat
```

Copy/paste values also live in [`scripts/9router/CURSOR_SETTINGS.txt`](../scripts/9router/CURSOR_SETTINGS.txt).

### Critical Cursor Agent limitation

Cursor **Agent** runs in Cursor’s **cloud**. Cloud requests cannot call `localhost` / private IPs. That produces:

```text
Access to private networks is forbidden
```

| Cursor feature | Can use `http://127.0.0.1:20128/v1`? | What to set |
|----------------|--------------------------------------|-------------|
| Local custom OpenAI models (IDE chat) | Sometimes yes | Localhost + 9Router key |
| **Agent / cloud agent loop** | **No** | Public HTTPS tunnel **or** disable override |

### Local Cursor chat settings

**Cursor Settings → Models → API Keys**:

| Setting | Value |
|---------|-------|
| OpenAI API Key | ON + paste **9Router dashboard key** |
| Override OpenAI Base URL | ON |
| Base URL | `http://127.0.0.1:20128/v1` |

Add models and toggle ON (examples from Cursor OAuth / `cu/`):

```text
cu/claude-4.6-sonnet-medium-thinking
cu/claude-4.5-haiku
cu/gpt-5.3-codex
```

Select one of those models in the chat model picker, then restart Cursor.

### Cursor Agent + 9Router (public tunnel)

```bat
scripts\9router\start_9router.bat
scripts\9router\start_9router_public_tunnel.bat
```

Requires [`cloudflared`](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/) on PATH. Use the printed `https://….trycloudflare.com` URL:

| Setting | Value |
|---------|-------|
| Override OpenAI Base URL | ON |
| Base URL | `https://YOUR-TUNNEL-HOST/v1` |
| API Key | 9Router dashboard key |
| Model | `cu/...` as above |

Keep the tunnel window open while Agent is running.

### Claude Code CLI

Edit `%USERPROFILE%\.claude\config.json`:

```json
{
  "anthropic_api_base": "http://localhost:20128/v1",
  "anthropic_api_key": "your-9router-api-key"
}
```

Model: `kr/claude-sonnet-4.5` or your combo name.

## Step 5 — Route CALT through 9Router (optional)

CALT has its own tier gateway (`docs/LLM_GATEWAY.md`). To send study AI through 9Router:

1. Keep 9Router running.
2. In `.env`:

```env
OLLAMA_ENABLED=1
LLM_API_KEY=your-9router-api-key-from-dashboard
LLM_DEFAULT_TIER=medium
```

3. Copy example tiers:

```bat
copy data\llm_tiers.9router.example.json data\llm_tiers.json
```

4. Set model names to match your connected providers or combo names.
5. Restart backend → **Settings → AI / LLM gateway** for chain health.

Chain format (supported by CALT):

```text
openai:http://127.0.0.1:20128/v1:free-forever
openai:http://127.0.0.1:20128/v1:kr/claude-sonnet-4.5
```

## How it works

```text
┌─────────────┐     ┌─────────────┐
│   Cursor    │     │  CALT app   │
│ Claude Code │     │ notes/quiz  │
└──────┬──────┘     └──────┬──────┘
       └─────────┬─────────┘
                 │ http://localhost:20128/v1
                 ▼
         ┌───────────────────────┐
         │       9Router         │
         │ RTK (-20–40% tokens)  │
         │ Format translation    │
         │ Quota tracking        │
         │ 3-tier fallback       │
         └───────────┬───────────┘
                     │
       ┌─────────────┼─────────────┐
       ▼             ▼             ▼
  Subscription    Cheap         Free
  cc/, cx/        glm/          kr/, oc/
```

9Router software is **free** (MIT). Dashboard "costs" are estimates only — you pay providers directly. Kiro and OpenCode Free stay $0.

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/9router/install_9router.bat` | `npm install -g 9router` |
| `scripts/9router/start_9router.bat` | Foreground on port 20128 |
| `scripts/9router/start_9router_tray.bat` | Background system tray |
| `scripts/9router/open_dashboard.bat` | Open dashboard |
| `scripts/9router/verify_9router.bat` | Health check localhost:20128 |
| `scripts/9router/setup_cursor_9router.bat` | Interactive Cursor setup guide |
| `scripts/9router/start_9router_public_tunnel.bat` | Cloudflare quick tunnel for Agent |
| `scripts/9router/CURSOR_SETTINGS.txt` | Copy/paste Cursor settings |

CLI flags: `9router -p 20128 -n` (no browser), `9router -t` (tray).

## Docker (VPS / always-on)

```bash
docker run -d --name 9router -p 20128:20128 \
  -v "$HOME/.9router:/app/data" -e DATA_DIR=/app/data \
  decolua/9router:latest
```

Or from source: [github.com/decolua/9router](https://github.com/decolua/9router#readme)

## Troubleshooting

| Issue | Fix |
|-------|-----|
| "Language model did not provide messages" | Provider quota exhausted — use a combo with fallback tiers |
| Rate limiting mid-session | Add combo: `cc/...` → `glm/glm-5.1` → `kr/claude-sonnet-4.5` |
| OAuth token expired | Auto-refreshed; reconnect in Dashboard → Provider if stuck |
| Dashboard wrong port | `9router -p 20128` or set `PORT=20128` + `NEXT_PUBLIC_BASE_URL` |
| First login fails | Set `INITIAL_PASSWORD` in `.env`; fallback is `123456` |
| CALT auth error | Set `LLM_API_KEY` to 9Router dashboard key |
| Model not found | Use exact id from Dashboard → Models, or a combo name |
| High displayed costs | Display only — free providers (Kiro, OpenCode) cost $0 |

## API (smoke test)

```bash
curl http://localhost:20128/v1/models -H "Authorization: Bearer YOUR_KEY"
```

```bash
curl http://localhost:20128/v1/chat/completions \
  -H "Authorization: Bearer YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"model\":\"kr/claude-sonnet-4.5\",\"messages\":[{\"role\":\"user\",\"content\":\"hi\"}]}"
```

## Links

- [9Router README](https://github.com/decolua/9router#readme) (v0.5.20)
- [9router.com](https://9router.com/)
- CALT gateway: `docs/LLM_GATEWAY.md`
