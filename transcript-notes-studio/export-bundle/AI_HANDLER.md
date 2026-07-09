# AI Handler — How LLM Calls Work in Transcript Notes Studio

## What “AI handler” means in this repo

The **AI handler** is `backend/core/llm_gateway.py` (copied here as `backend_llm_gateway.py`).  
It is **not** a separate microservice — it is a Python module that:

1. Maps **tasks** (e.g. `corpus_grounded`, `note_enrich`) to **tiers** (`light` / `medium` / `heavy`).
2. Walks an **ordered provider chain** from `data/llm_tiers.json` / `data/llm_routes.*.json`.
3. Picks the first reachable provider (LM Studio, Ollama, OpenRouter, etc.).
4. Applies **capability filters** (JSON schema, system prompt).
5. Enforces **heavy-tier budget** for cloud calls.
6. **Falls back** on rate limit, timeout, empty response, etc.
7. Logs structured lines: `llm_call task=... tier=... provider=... latency_ms=...`

Transport layer: `backend_ollama_client.py` — actual HTTP to LM Studio `/api/v1/chat`, Ollama `/api/generate`, etc.

---

## Call flow (RAG generate)

```
gui._run_summarize()
  → notes_generator.generate_notes_from_file()
      → backend note_generation.generate_notes_unified()
          → hybrid_notes / grounded_notes
              → ollama_generate(prompt, task="corpus_grounded", tier=...)
                  → llm_gateway.generate_text(...)
                      → resolve chain for tier "heavy" (corpus_grounded default)
                      → llm_reachable(entry) per chain link [cached 20s]
                      → ollama_generate_transport() → POST LM Studio
                  → chunk_polish.finalize_full_note()
                      → note_enrich (task="note_enrich", tier medium)
```

**Log example (success):**

```
llm_call task=corpus_grounded tier=custom provider=lmstudio model=google/gemma-4-e4b fallback=False latency_ms=35998 error=none
```

---

## Task → tier defaults (`TASK_DEFAULTS`)

| Task | Default tier | Studio usage |
|------|--------------|--------------|
| `corpus_grounded` | **heavy** | RAG single-shot + hybrid chunk summaries |
| `note_enrich` | medium | Mermaid/code after full note merged |
| `notes_chunk` | medium | Legacy chunk summarization (web API) |
| `notes_refine` | medium | Second-pass refine |
| `quiz_gen` | medium | Web quiz (not Studio) |
| `coach` | light | Hub coach (not Studio) |

Studio Generate (RAG path) primarily hits **`corpus_grounded`** and optionally **`note_enrich`**.

---

## Studio path that bypasses the AI handler

When RAG is unavailable or `legacy_notes_pipeline=true`:

```
notes_generator.generate_notes_from_text()
  → studio_generate(prompt) = llm_client.generate()
      → direct httpx POST to LM Studio (no tier, no task, no fallback chain)
```

**Why two paths exist:**

- Studio was built first with a **thin local client** (`llm_client.py`).
- Backend/web app got **gateway** for multi-provider routing and cloud budgets.
- RAG code lives in `backend/` and naturally uses the gateway.
- Legacy fallback still uses Studio client for speed and semantic cache.

**Improvement options:**

1. Make `studio_generate` call `ollama_generate(..., task="notes_chunk")` instead of `llm_client.generate`.
2. Or delete legacy path once RAG is always reliable.

---

## Reachability checks (`llm_reachable`)

Before generate, Studio checks LM Studio:

- `llm_client.llm_reachable()` — status bar + pre-flight in `_run_summarize`
- `ollama_available()` → `gateway_available()` — backend path

Both ping `GET http://127.0.0.1:1234/api/v1/models` (LM Studio).  
**Cached 20 seconds** to avoid request loops in logs.

`gateway_available()` without override walks **all tiers** — expensive; Studio now avoids double-check in `rag_status.py`.

---

## Configuration files (monorepo, not in bundle)

| File | Purpose |
|------|---------|
| `data/llm_tiers.json` | Provider chains per tier |
| `data/llm_routes.*.json` | Route profiles (hybrid, openrouter) |
| `.env` / `backend/config.py` | `OLLAMA_ENABLED`, default URLs |
| `transcript-notes-studio/config.json` | Studio UI: provider, model, fast_mode |

Studio `config.json` **overrides** are passed as `LlmOptions` into backend when generating RAG notes.

---

## RAG + AI handler together

1. **Retrieve** (`backend_retrieve.py`): hybrid BM25 + Qdrant, filter `source_type=textbook`.
2. **Prompt**: transcript chunk + formatted reference chunks + citation rules.
3. **Generate**: `task=corpus_grounded` via gateway → LM Studio Gemma.
4. **Polish**: strip LLM preamble, repair fences.
5. **Enrich** (if not fast_mode): `task=note_enrich` adds mermaid/code; shrink guard keeps original if model returns garbage.
6. **Handoff**: optional ingest of transcript + note into corpus for **quiz** (not used during step 1–3 retrieval).

---

## Debugging AI handler issues

| Symptom | Check |
|---------|--------|
| `LLM not reachable` | LM Studio running? Model loaded? `config.json` URL |
| `llm_tier is not defined` | `backend_grounded_notes.py` signature |
| Empty chunk / timeout | Reduce chunks (`fast_mode`), raise timeout, check `max_llm_chunks` |
| Chain-of-thought in notes | `note_enrich` guard; disable enrich or use fast_mode |
| Many GET /models | reachability cache; reduce status poll frequency |
| RAG cites wrong domain | textbook filter OK; transcript chunks in registry are normal |

**Logs:** `data/logs/transcript_studio.log` (GUI), `data/logs/notes_generation.log` (backend), LM Studio own log panel.
