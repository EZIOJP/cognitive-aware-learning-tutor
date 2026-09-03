# AI Handler — overview

CALT routes study AI (notes, quiz, block repair, coach, classification) through a **single backend gateway** and a **thin frontend bridge**. There is no class named `AIHandler`; the name refers to this subsystem as a whole.

## Mental model

```text
Browser (tier prefs)  →  transcriptsClient.ts  →  FastAPI routers  →  domain code
                                                              ↓
                                                    ollama_generate()
                                                              ↓
                                                    llm_gateway.llm_complete()
                                                              ↓
                                         LM Studio / Gemini / Ollama / OpenAI-compat
```

**Users pick a tier** (`light` / `medium` / `heavy`). **Operators configure chains** in `data/llm_tiers.json` and `.env`. API keys are edited in **Settings → AI Control Center** or Notes Studio (writes `.env`, hot reload).

## Read next

| Doc | Audience | Contents |
|-----|----------|----------|
| [AI_HANDLER_BACKEND.md](AI_HANDLER_BACKEND.md) | Python / API work | Gateway modules, call flow, tasks, endpoints, config |
| [AI_HANDLER_FRONTEND.md](AI_HANDLER_FRONTEND.md) | React / UI work | Prefs, pages, API calls, localStorage, known gaps |
| [LLM_GATEWAY.md](LLM_GATEWAY.md) | Ops / config | Tier chains, env vars, failure policy, 9Router |
| [LOCAL_LLM_NOTES_GUIDE.md](LOCAL_LLM_NOTES_GUIDE.md) | Quality tuning | Presets, CPU/GPU, note-generation behavior |

## Where code lives

### Backend (canonical)

| Path | Role |
|------|------|
| `backend/core/llm_gateway.py` | **AI handler core** — routing, fallback, budget |
| `backend/core/ollama_client.py` | HTTP transport (misnamed: not Ollama-only) |
| `backend/core/llm_tiers.py` | Parses `data/llm_tiers.json` |
| `backend/core/llm_routes.py` | Route profiles from `data/llm_routes.json` |
| `backend/transcripts/router.py` | Study HTTP API + `GET /llm-config` |
| `backend/transcripts/note_generation.py` | Notes entry (RAG vs legacy) |

### Frontend (canonical)

| Path | Role |
|------|------|
| `src/api/transcriptsClient.ts` | **FE AI bridge** — prefs, config fetch, `llmBodyFields` |
| `src/pages/settings/AiControlCenterPage.tsx` | Settings → keys, test connections, tiers |
| `src/pages/study/LectureNotesPage.tsx` | Study Library — tier UI + generate/regen actions |

### Config (server-side)

| Path | Role |
|------|------|
| `data/llm_tiers.json` | Active provider chains per tier |
| `data/llm_routes.json` | Optional profile overrides (`hybrid`, `9router`, …) |
| `.env` | `LLM_CLOUD_API_KEY`, `OLLAMA_ENABLED`, `LLM_DEFAULT_TIER`, … |

## What uses the gateway today

| Feature | Backend module | Default task tier |
|---------|----------------|-------------------|
| Generate notes | `note_generation` → `hybrid_notes` / `notes_generator` | medium |
| Grounded RAG notes | `corpus/grounded_notes` | heavy (`corpus_grounded`) |
| GRE vocab card enrich | `vocab/enrich` (funny mnemonic + examples) | medium (`vocab_enrich`) |
| Quiz / drills / gap analysis | `study_intel` | medium |
| Block regen / repair | `block_regenerate`, `note_block_repair` | medium |
| Study flow orchestrator | `study_flow` | medium (sticky job) |
| App classification | `behavior/classification_service` | light |
| Math tutor hints (text) | `math/ollama_tutor` | light (`math_hint`) |
| Daily AI review | `hub/services/gemma_review` | heavy (`daily_review`) |

## Explicitly outside the gateway (for now)

| Path | Why |
|------|-----|
| `backend/math/ollama_tutor.py` (vision branch) | Direct Ollama multimodal when `OLLAMA_VISION_MODEL` + canvas image |
| `backend/integrations/nim_client.py` | OCR vision teacher labels only (`nim_vision_latex`) |
| `transcript-notes-studio/` | Desktop app — shares repo gateway + `.env` key editor |

## Key & test API

- `PATCH /api/system/llm/keys` — update whitelisted `.env` vars (JWT)
- `POST /api/system/llm/test-chain` — probe each provider in a tier chain
- `POST /api/insights/review` — daily insights review (template or local LLM)

## Quick health check

1. Start LM Studio (or set cloud keys in `.env`).
2. `OLLAMA_ENABLED=1` in `.env`, restart backend.
3. Open **Settings → AI Control Center** — save keys, **Test all tiers**.
4. `GET /api/transcripts/llm-config` (with JWT) returns `reachable: true` for at least one tier.

## Related tests

- `tests/test_llm_gateway.py`
- `tests/test_env_store.py`
- `tests/test_llm_budget.py`
- `tests/test_ollama_client.py`
- `tests/test_math_tutor_gateway.py`
- `tests/test_daily_review_gateway.py`
