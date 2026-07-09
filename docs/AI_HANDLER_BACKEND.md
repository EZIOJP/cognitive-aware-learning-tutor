# AI Handler — backend

How LLM calls work on the server: modules, request flow, tasks, and where to add new AI features.

See also: [AI_HANDLER.md](AI_HANDLER.md) (overview), [LLM_GATEWAY.md](LLM_GATEWAY.md) (config).

---

## Core rule

**Domain code calls `ollama_generate()`, never `llm_complete()` directly.**

`ollama_generate` in `backend/core/ollama_client.py` is the public façade. It delegates to `llm_complete()` in `backend/core/llm_gateway.py`, which walks the tier chain and invokes transport.

```python
# Correct pattern in any backend module
from backend.core.ollama_client import ollama_generate

text = ollama_generate(
    prompt,
    task="quiz_gen",           # maps to default tier + capabilities
    tier=llm_tier,             # optional override from request body
    llm=llm_options,           # optional per-request provider override
    confirm_heavy_budget=True, # required after heavy cap prompt
)
```

---

## Module map

```text
backend/core/
├── llm_gateway.py      ← AI handler: llm_complete(), TASK_DEFAULTS, fallback, logging
├── ollama_client.py    ← Transport: LM Studio, Ollama, Gemini, OpenAI-compat URLs
├── llm_tiers.py        ← Parse data/llm_tiers.json chains
├── llm_routes.py       ← Profile selector (data/llm_routes.json)
├── llm_capabilities.py ← Filter chain by JSON schema / system prompt needs
├── llm_budget.py       ← Heavy-tier daily soft cap (data/llm_usage/)
├── llm_job_context.py  ← ContextVar: sticky tier for multi-chunk jobs
└── llm_router.py       ← POST /api/llm/complete (scripts/tools)

backend/transcripts/
├── router.py           ← HTTP: llm-config, notes, quiz, regen, study-flow
├── note_generation.py  ← Unified notes (RAG if corpus+LLM up, else legacy)
├── hybrid_notes.py     ← Chunked corpus-grounded notes
├── notes_generator.py  ← Legacy transcript-only summarization
├── study_intel.py      ← quiz_gen, drill_gen, gap_analysis
├── study_flow.py       ← Orchestrator: notes → quiz → optional SRS session
├── note_enrich.py      ← Mermaid/code enrich (note_enrich)
└── block_regenerate.py ← Block regen/repair (block_regen)

backend/corpus/
├── grounded_notes.py   ← Single-shot RAG (corpus_grounded task)
└── router.py           ← POST /api/corpus/generate-notes-grounded

backend/hub/services/
└── local_coach.py      ← Coach chat (coach task)

backend/behavior/
└── classification_service.py  ← Window/app classify (classify task)
```

---

## Request flow (notes generation)

```text
POST /api/transcripts/notes/generate
  body: { transcript_file, llm_tier?, llm_provider?, confirm_heavy_budget?, ... }
    │
    ▼
transcripts/router.py
  _tier_from_body() → llm_tier
  _llm_override_from_body() → LlmOptions (legacy per-request override)
  _guard_heavy_budget() → 402 if heavy cap exceeded without confirm
    │
    ▼
note_generation.generate_notes_unified()
  ├─ [corpus + LLM available] hybrid_notes.generate_grounded_notes_smart()
  │     with llm_job(tier, task="notes_job"):   # locks tier for all chunks
  │       per chunk: hybrid_retrieve → summarize_chunk()
  │         → ollama_generate(task="notes_chunk")
  │       optional refine → ollama_generate(task="notes_refine")
  │       optional enrich → note_enrich (task="note_enrich")
  └─ [else] notes_generator.generate_notes_from_file()
        → same ollama_generate path

ollama_generate()
  → llm_complete()
       1. Resolve tier: job context > request tier > TASK_DEFAULTS[task]
       2. get_chain_for_tier() from llm_routes or llm_tiers
       3. capability_filter() for task requirements
       4. For each ChainEntry:
            llm_reachable() → ollama_generate_transport()
            on 429/5xx/timeout → try next entry
       5. record_heavy_cloud_call() if cloud + heavy
       6. Log: llm_call task=... tier=... provider=... latency_ms=...
```

---

## Task → tier defaults

Defined in `llm_gateway.TASK_DEFAULTS`:

| Task | Tier | Notes |
|------|------|-------|
| `notes_chunk`, `notes_refine`, `notes_job` | medium | Chunked notes |
| `note_enrich`, `block_regen` | medium | Post-process |
| `corpus_grounded` | heavy | RAG single-shot / hybrid summaries |
| `quiz_gen`, `drill_gen`, `gap_analysis` | medium | JSON output required |
| `coach`, `classify`, `kg_anchor`, `memory_extract` | light | Fast / local-biased |
| `project_agent` | medium | Codebase agent |
| `generic` | medium | `/api/llm/complete` default |

When adding a new AI feature, pick an existing task or add one entry here with appropriate `LlmRequirements`.

---

## HTTP endpoints that accept LLM params

All study endpoints share optional body fields (see `LlmFieldsMixin` patterns in `transcripts/router.py`):

| Field | Purpose |
|-------|---------|
| `llm_tier` | `light` / `medium` / `heavy` |
| `llm_provider` | Legacy override (`lmstudio`, `gemini`, `ollama`) |
| `llm_base_url` | Legacy override URL |
| `llm_model` | Legacy override model id |
| `confirm_heavy_budget` | User confirmed heavy-tier cloud spend |

| Endpoint | Handler |
|----------|---------|
| `GET /api/transcripts/llm-config` | `get_gateway_config()` + reachability per tier |
| `POST /api/transcripts/notes/generate` | `generate_notes_unified` |
| `POST /api/transcripts/study-flow/start` | `run_topic_study_flow` |
| `POST /api/transcripts/library/generate-quiz` | `generate_quiz_items` |
| `POST /api/transcripts/library/regenerate-block` | `block_regenerate` |
| `POST /api/corpus/generate-notes-grounded` | `grounded_notes` (should accept same LLM fields) |
| `POST /api/llm/complete` | Generic completion (`llm_router.py`) |
| `POST /api/insights/chat` | Coach (no tier from client today) |

---

## Configuration resolution order

1. **Per-request override** — `llm_provider` / `llm_base_url` / `llm_model` in JSON body (legacy; prefer tier only).
2. **Request tier** — `llm_tier` in body or query (`llm-config`).
3. **Job context** — `llm_job()` ContextVar for long note jobs.
4. **Task default** — `TASK_DEFAULTS[task][0]`.
5. **Env default** — `LLM_DEFAULT_TIER` (usually `medium`).

Chain for a tier:

1. `data/llm_routes.json` profile (`LLM_ROUTE_PROFILE`) if file exists.
2. Else `data/llm_tiers.json`.
3. Else env `LLM_TIER_LIGHT|MEDIUM|HEAVY`.

Chain entry format:

```text
lmstudio:google/gemma-4-e4b
gemini:gemini-2.5-pro
openai:https://openrouter.ai/api/v1:anthropic/claude-sonnet-4
ollama:llama3.2:3b
```

---

## Failure and fallback

| Condition | Behavior |
|-----------|----------|
| 429, 5xx, timeout, auth, empty response | Retry once on same entry, then next chain link |
| Gemini rate limit | 180s cloud cooldown → skip cloud, use local |
| `context_too_long` | **No fallback** — caller must chunk |
| `budget_exceeded` (heavy cap) | **No fallback** — return 402; client sends `confirm_heavy_budget` |
| `OLLAMA_ENABLED=0` | Gateway off; notes fall back to `legacy_llm_off` mode |

Logs look like:

```text
llm_call task=notes_chunk tier=medium provider=lmstudio model=google/gemma-4-e4b fallback=False latency_ms=4200 error=none
```

---

## Adding a new backend AI feature

1. Implement logic in the right domain folder (`transcripts/`, `corpus/`, `hub/`).
2. Call `ollama_generate(..., task="your_task")`.
3. Add `your_task` to `TASK_DEFAULTS` if it needs a non-medium tier or JSON schema.
4. Expose via router with `llm_tier` + `confirm_heavy_budget` on the request model.
5. Add FE call in `transcriptsClient.ts` with `llmBodyFields()`.
6. Add test in `tests/test_llm_gateway.py` or domain test with mocked transport.

**Do not** add a parallel HTTP client to LM Studio or Gemini in feature code.

---

## Out of scope (migrate later)

| Module | Current behavior |
|--------|------------------|
| `backend/math/ollama_tutor.py` | Direct httpx to Ollama |
| `backend/integrations/nim_client.py` | NVIDIA NIM for coach review |
| `transcript-notes-studio/transcript_studio/llm_client.py` | Studio-only thin client |

---

## Debugging checklist

| Symptom | Check |
|---------|-------|
| 503 LLM unreachable | `OLLAMA_ENABLED=1`, LM Studio running, `GET /llm-config` |
| Always uses local, never Gemini | Chain order in `llm_tiers.json`, `LLM_CLOUD_API_KEY` set |
| Heavy calls blocked | `data/llm_usage/`, `confirm_heavy_budget` in request |
| Tier changes mid-note-job | Should not — verify `llm_job()` wraps the job |
| Wrong provider despite tier | Legacy `llm_provider` override in request body |
| Corpus path ignores tier | `corpus/router.py` may not read `llm_tier` from body yet |
