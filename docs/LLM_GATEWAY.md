# LLM Gateway — tiered provider chains

Central routing for all AI calls (notes, quiz, coach, classification + external scripts). One gateway, ordered fallbacks, capability-aware routing.

**Developer guides:** [AI_HANDLER.md](AI_HANDLER.md) (overview) · [AI_HANDLER_BACKEND.md](AI_HANDLER_BACKEND.md) · [AI_HANDLER_FRONTEND.md](AI_HANDLER_FRONTEND.md)

## Tiers

| Tier | Typical use | Default chain (see `data/llm_tiers.json`) |
|------|-------------|-------------------------------------------|
| `light` | Fast / free / local | LM Studio |
| `medium` | Daily driver | Gemini → LM Studio → Ollama |
| `heavy` | Best quality (paid) | Gemini Pro → **NIM** (`integrate.api.nvidia.com`) → Claude/OpenRouter → LM Studio |

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
LLM_ROUTE_PROFILE=local

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
NIM_API_KEY=nvapi-...  # optional: heavy-tier NIM chain + math OCR vision
```

API keys stay server-side in `.env`. Edit them in **Settings → AI Control Center** (browser) or Notes Studio — both write to repo `.env` with hot reload.

```env
TAVILY_API_KEY=tvly-...  # optional: Cortex Hub web search agent
```

## Key management API (JWT)

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/system/llm/env` | Masked key status + route profile |
| `PATCH` | `/api/system/llm/keys` | Update whitelisted `.env` vars |
| `POST` | `/api/system/llm/test` | Probe one provider entry |
| `POST` | `/api/system/llm/test-chain` | Probe every entry in a tier chain |
| `POST` | `/api/system/llm/test-all-profiles` | Enqueue matrix probe → `202 { job_id }` (Huey) |
| `GET` | `/api/system/llm/jobs/{id}` | Poll job status / result |

## Cortex Hub

Multi-agent chat at `/hub` — routes to coach, corpus RAG, project agent, Tavily search, ephemeral PDF Q&A.

- `GET /api/insights/hub/agents` — agent modes
- `POST /api/insights/hub/chat` — multipart (prompt, agent, optional PDF file)

Gateway tasks: `hub_router`, `corpus_qa`, `web_search`.

## OpenRouter (native routing)

When consecutive chain entries target OpenRouter, CALT sends **one** request with OpenRouter's native `models[]` fallback array instead of walking each model separately.

| CALT layer | OpenRouter feature |
|------------|-------------------|
| `data/llm_routes.json` consecutive `openrouter:*` entries | `models: [primary, ...fallbacks]` |
| Tier `light` / `medium` / `heavy` | `provider.sort`: latency / price / throughput |
| `quiz_gen` + JSON schema | `provider.require_parameters: true` |
| Notes jobs (`llm_job` context) | Top-level `session_id` + `x-session-id` header (sticky routing per [OpenRouter API](https://openrouter.ai/docs/api/api-reference/chat/create-a-chat-completion)) — **not** inside `provider` |
| Router debug | `X-OpenRouter-Metadata: enabled` → log `openrouter_metadata` (strategy, attempt, attempts[]) |
| Heavy tier cost cap | `provider.max_price` from `LLM_OPENROUTER_MAX_PRICE_*` |
| Batch vs interactive | `service_tier: flex` (notes/quiz) vs `priority` (coach/hub) |
| Repeated quiz prompts | `X-OpenRouter-Cache: enabled` on cache-eligible tasks |
| Sensitive profiles | `LLM_OPENROUTER_ZDR=1` → `provider.zdr: true` |
| Dashboard presets | Model slug `@preset/calt-medium` in `llm_routes.json` (no deploy) |
| Zero-completion errors | `finish_reason: error` / 0 completion tokens logged as not billed |

Optional `.env`:

```env
LLM_OPENROUTER_PROVIDER_SORT=latency   # or throughput, price
LLM_OPENROUTER_DATA_COLLECTION=deny
LLM_OPENROUTER_METADATA=1
LLM_OPENROUTER_RESPONSE_CACHE=1
LLM_OPENROUTER_ZDR=0
LLM_OPENROUTER_MAX_PRICE_PROMPT=0.001
LLM_OPENROUTER_MAX_PRICE_COMPLETION=0.002
LLM_OPENROUTER_MAX_LATENCY_LIGHT=2.0
LLM_OPENROUTER_MAX_LATENCY_MEDIUM=8.0
```

Use `openrouter:openrouter/auto` in a chain entry for OpenRouter's auto model picker.

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
| `backend/core/llm_jobs.py` | Huey SqliteHuey queue + job status files |
| `backend/core/llm_jobs_worker.py` | Consumer: `python -m backend.core.llm_jobs_worker` |
| `backend/core/ollama_client.py` | HTTP transport per provider |
| `backend/core/llm_router.py` | External completion API (`/api/llm/complete`) |

## Tasks (default tier)

| Task | Default tier | Notes |
|------|-------------|-------|
| `coach`, `classify`, `math_hint` | light | Interactive / fast |
| `quiz_gen`, `notes_*`, `block_regen`, … | medium | Daily study work |
| `concept_extract` | light | Atomic concepts for retrieve / quiz split |
| `corpus_grounded`, `daily_review` | heavy | Quality + cloud budget |

## Out of scope

- Math tutor **vision** path (`OLLAMA_VISION_MODEL` + canvas) — direct Ollama only
- `nim_client.nim_vision_latex` — OCR teacher labels (not gateway)
- Generic browser prompt API
- Async **note** generation (stays sync). Huey is used only for long chain probes (`test-all-profiles`).

### Huey worker (profile matrix) — required for Test all route profiles

**Start this in a second terminal before using AI Control Center → “Test all route profiles”:**

```bat
python -m backend.core.llm_jobs_worker
```

Without the worker, `POST /api/system/llm/test-all-profiles` still returns `202 { job_id }`, but the job never leaves `queued` / `pending` (status files under `data/llm_jobs/`). Queue DB: `data/huey.db`.

Under pytest, Huey runs in `immediate` mode (`HUEY_IMMEDIATE=1` in `tests/conftest.py`) so no worker is needed for CI. Single-tier `test-chain` stays synchronous and does not use Huey. Note generation stays synchronous.

## 9Router (external)

For **Cursor / Claude Code** unlimited sessions with free-provider fallback, use [9Router](https://github.com/decolua/9router) v0.5.20+ separately — see [9ROUTER_SETUP.md](9ROUTER_SETUP.md). Free tiers (2026): Kiro (`kr/`) + OpenCode Free (`oc/`). CALT can route tier chains through `http://127.0.0.1:20128/v1` via `data/llm_tiers.9router.example.json`.
