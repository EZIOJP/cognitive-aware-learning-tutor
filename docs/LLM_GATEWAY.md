# LLM Gateway — tiered provider chains

Central routing for all AI calls (notes, quiz, coach, classification + external scripts). One gateway, ordered fallbacks, capability-aware routing.

**Developer guides:** [AI_HANDLER.md](AI_HANDLER.md) (overview) · [AI_HANDLER_BACKEND.md](AI_HANDLER_BACKEND.md) · [AI_HANDLER_FRONTEND.md](AI_HANDLER_FRONTEND.md)

## Tiers

| Tier | Typical use | Default chain (see `data/llm_tiers.json`) |
|------|-------------|-------------------------------------------|
| `light` | Fast / free / local | LM Studio |
| `medium` | Daily driver | Gemini → LM Studio → Ollama |
| `heavy` | Best quality (paid) | Gemini Pro → Claude → LM Studio |

Edit chains in [`data/llm_tiers.json`](../data/llm_tiers.json) without code changes, or activate route profiles via `data/llm_routes.json`.

## Route profiles

`LLM_ROUTE_PROFILE` picks an active chain profile (`hybrid`, `9router`, `openrouter`, `local`) from `data/llm_routes.json`.

- If `data/llm_routes.json` is missing, gateway falls back to `data/llm_tiers.json`.
- Example presets:
  - [`data/llm_routes.hybrid.example.json`](../data/llm_routes.hybrid.example.json)
  - [`data/llm_routes.openrouter.example.json`](../data/llm_routes.openrouter.example.json)

Chain entry format:

```text
provider:model
provider:https://api.example.com/v1:model-name
ollama:llama3.2:3b
```

## Configuration (`.env`)

```env
OLLAMA_ENABLED=1
LLM_DEFAULT_TIER=medium
LLM_ROUTE_PROFILE=hybrid

# Optional env overrides (used if llm_tiers.json missing)
LLM_TIER_LIGHT=lmstudio:google/gemma-4-e4b
LLM_TIER_MEDIUM=gemini:gemini-2.0-flash,lmstudio:google/gemma-4-e4b
LLM_TIER_HEAVY=gemini:gemini-2.5-pro,openai:https://api.anthropic.com/v1:claude-3-5-sonnet-20241022

LLM_CLOUD_API_KEY=your-gemini-key
LLM_ANTHROPIC_API_KEY=sk-ant-...
LLM_OPENROUTER_API_KEY=sk-or-v1-...
LLM_OPENROUTER_SITE_URL=https://your-app.example
LLM_OPENROUTER_APP_NAME=CALT
LLM_HEAVY_DAILY_SOFT_CAP=50
```

API keys stay server-side only. The web UI selects **tier**, not keys.

## Failure policy

| Error | Fallback to next provider? |
|-------|---------------------------|
| 429, 5xx, timeout, auth, empty | Yes (1 retry on same entry first) |
| `context_too_long` | **No** — caller must chunk |
| `budget_exceeded` (heavy cap) | **No** — lower tier or `confirm_heavy_budget` |

## Job-sticky tier

Multi-chunk notes jobs lock tier at start (`llm_job` context). Manual override in the request body is resolved once; chunks do not re-pick providers mid-job.

## API

- `GET /api/transcripts/llm-config` — tiers, health, active route profile, heavy budget, last call log
- Request bodies accept `llm_tier` and `confirm_heavy_budget`
- `POST /api/llm/complete` — JWT-protected generic completion endpoint for scripts/tools

## UI

**Settings → AI / LLM gateway** — default tier, chain health, heavy usage.

**Study Library** — tier dropdown (light / medium / heavy).

## Implementation

| Module | Role |
|--------|------|
| `backend/core/llm_gateway.py` | `llm_complete()`, routing, logging |
| `backend/core/llm_routes.py` | Profile-based chain selector |
| `backend/core/llm_tiers.py` | Chain parsing |
| `backend/core/llm_capabilities.py` | Provider capability filter |
| `backend/core/llm_budget.py` | Heavy-tier daily soft cap |
| `backend/core/llm_job_context.py` | Sticky tier for long jobs |
| `backend/core/ollama_client.py` | HTTP transport per provider |
| `backend/core/llm_router.py` | External completion API (`/api/llm/complete`) |

## Out of scope

- `backend/math/ollama_tutor.py` (separate path; migrate later)
- Generic browser prompt API
- Async job queue (corpus jobs unchanged)

## 9Router (external)

For **Cursor / Claude Code** unlimited sessions with free-provider fallback, use [9Router](https://github.com/decolua/9router) v0.5.20+ separately — see [9ROUTER_SETUP.md](9ROUTER_SETUP.md). Free tiers (2026): Kiro (`kr/`) + OpenCode Free (`oc/`). CALT can route tier chains through `http://127.0.0.1:20128/v1` via `data/llm_tiers.9router.example.json`.
