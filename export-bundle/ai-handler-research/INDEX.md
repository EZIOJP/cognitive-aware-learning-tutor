# AI Handler Research Export — File Index

**Bundle:** `export-bundle/ai-handler-research/`  
**Created:** 2026-07-09  
**Purpose:** Offline research copy for Google Drive — exact copies of live repo files (same relative paths).

**Monorepo root:** `Cognitive-Aware Learning Tutor`

---

## How to use this bundle

1. Read **`docs/AI_HANDLER.md`** — overview and mental model.
2. Pick your track:
   - **Backend:** `docs/AI_HANDLER_BACKEND.md` → `backend/core/llm_gateway.py`
   - **Frontend:** `docs/AI_HANDLER_FRONTEND.md` → `src/api/transcriptsClient.ts`
3. **Config:** `data/llm_tiers.json` + `.env.example` + `docs/LLM_GATEWAY.md`
4. **Trace a request:** FE `generateNotes()` → BE `transcripts/router.py` → `note_generation.py` → `ollama_generate()` → `llm_gateway.py`

---

## Summary

| Category | Files | Role |
|----------|------:|------|
| Documentation | 6 | Explain architecture, FE/BE flow, ops |
| Backend core | 10 | Gateway, transport, tiers, routes, budget |
| Backend domain | 12 | Notes, quiz, corpus, coach, classification |
| Frontend | 12 | API client, settings, study UI |
| Config / data | 5 | Tier chains, route examples, env template |
| Tests | 3 | Gateway, budget, transport unit tests |
| **Total** | **49** | |

---

## Documentation (6)

| # | Export path | Live path | Description |
|---|-------------|-----------|-------------|
| 1 | `docs/AI_HANDLER.md` | same | Overview — what “AI handler” means, file map |
| 2 | `docs/AI_HANDLER_BACKEND.md` | same | Backend modules, call flow, tasks, endpoints |
| 3 | `docs/AI_HANDLER_FRONTEND.md` | same | Frontend prefs, UI, API calls, known gaps |
| 4 | `docs/LLM_GATEWAY.md` | same | Tier chains, env vars, failure policy |
| 5 | `docs/LOCAL_LLM_NOTES_GUIDE.md` | same | Local models, quality presets for notes |
| 6 | `docs/9ROUTER_SETUP.md` | same | Optional external router (Cursor + CALT) |

---

## Backend — core gateway (10)

| # | Export path | Live path | Description |
|---|-------------|-----------|-------------|
| 7 | `backend/core/llm_gateway.py` | same | **AI handler core** — `llm_complete()`, fallback, logging |
| 8 | `backend/core/ollama_client.py` | same | HTTP transport (LM Studio, Gemini, Ollama, OpenAI-compat) |
| 9 | `backend/core/llm_tiers.py` | same | Parse `data/llm_tiers.json` chains |
| 10 | `backend/core/llm_routes.py` | same | Route profiles from `data/llm_routes.json` |
| 11 | `backend/core/llm_capabilities.py` | same | JSON schema / system-prompt filters |
| 12 | `backend/core/llm_budget.py` | same | Heavy-tier daily soft cap |
| 13 | `backend/core/llm_job_context.py` | same | Sticky tier for multi-chunk note jobs |
| 14 | `backend/core/llm_router.py` | same | `POST /api/llm/complete` for scripts |
| 15 | `backend/config.py` | same | `LLM_*` / `OLLAMA_*` settings |
| 16 | `backend/paths.py` | same | `LLM_TIERS_PATH`, `LLM_ROUTES_PATH` |

---

## Backend — domain callers (12)

| # | Export path | Live path | Description |
|---|-------------|-----------|-------------|
| 17 | `backend/transcripts/router.py` | same | HTTP API: `llm-config`, notes, quiz, regen, study-flow |
| 18 | `backend/transcripts/note_generation.py` | same | Unified notes entry (RAG vs legacy) |
| 19 | `backend/transcripts/hybrid_notes.py` | same | Chunked corpus-grounded notes |
| 20 | `backend/transcripts/notes_generator.py` | same | Legacy transcript-only summarization |
| 21 | `backend/transcripts/study_intel.py` | same | Quiz, drills, gap analysis |
| 22 | `backend/transcripts/study_flow.py` | same | Orchestrator: notes → quiz → SRS |
| 23 | `backend/transcripts/note_enrich.py` | same | Mermaid/code enrich pass |
| 24 | `backend/transcripts/block_regenerate.py` | same | Block regen/repair |
| 25 | `backend/transcripts/note_block_repair.py` | same | Repair orchestration |
| 26 | `backend/corpus/grounded_notes.py` | same | Single-shot RAG notes |
| 27 | `backend/corpus/router.py` | same | `POST /api/corpus/generate-notes-grounded` |
| 28 | `backend/hub/services/local_coach.py` | same | Coach chat (`task=coach`) |
| 29 | `backend/behavior/classification_service.py` | same | App/window classification |

---

## Frontend (12)

| # | Export path | Live path | Description |
|---|-------------|-----------|-------------|
| 30 | `src/api/transcriptsClient.ts` | same | **FE AI bridge** — prefs, `getLlmConfig`, study POSTs |
| 31 | `src/api/corpusClient.ts` | same | Grounded notes API (tier gap documented) |
| 32 | `src/pages/settings/LlmGatewayCard.tsx` | same | Settings → tier + chain health |
| 33 | `src/pages/settings/NineRouterCard.tsx` | same | 9Router setup card |
| 34 | `src/pages/settings/SettingsHubPage.tsx` | same | Settings hub shell |
| 35 | `src/pages/study/LectureNotesPage.tsx` | same | Study Library — tier UI, generate, regen |
| 36 | `src/pages/study/TopicStudyFlowPage.tsx` | same | Topic study flow stepper |
| 37 | `src/components/study/StudyLibraryCreateSheet.tsx` | same | New note sheet; LLM reachability |
| 38 | `src/components/study/StudyLibraryViewer.tsx` | same | Note viewer; online/offline badge |
| 39 | `src/components/study/useSectionBlockEdit.tsx` | same | Block edit + regen hook |
| 40 | `src/components/study/useSelectionRegenerate.tsx` | same | Selection regen hook |
| 41 | `src/components/study/SectionBlockToolbar.tsx` | same | Fix-with-AI toolbar buttons |

---

## Config & data (5)

| # | Export path | Live path | Description |
|---|-------------|-----------|-------------|
| 42 | `data/llm_tiers.json` | same | Active provider chains (light/medium/heavy) |
| 43 | `data/llm_routes.hybrid.example.json` | same | Example route profiles (copy → `llm_routes.json`) |
| 44 | `data/llm_tiers.9router.example.json` | same | 9Router chain example |
| 45 | `data/llm_routes.openrouter.example.json` | same | OpenRouter profile example |
| 46 | `.env.example` | same | Env template (no secrets) |

---

## Tests (3)

| # | Export path | Live path | Description |
|---|-------------|-----------|-------------|
| 47 | `tests/test_llm_gateway.py` | same | Gateway routing / fallback tests |
| 48 | `tests/test_llm_budget.py` | same | Heavy-tier cap tests |
| 49 | `tests/test_ollama_client.py` | same | Transport layer tests |

---

## Request flow (quick reference)

```text
Browser
  loadLlmPrefs() / saveLlmPrefs()     [src/api/transcriptsClient.ts]
  GET  /api/transcripts/llm-config    [backend/transcripts/router.py]
  POST /api/transcripts/notes/generate
       │
       ▼
  note_generation.generate_notes_unified()
       │
       ▼
  ollama_generate(task=...)             [backend/core/ollama_client.py]
       │
       ▼
  llm_complete()                        [backend/core/llm_gateway.py]
       │
       ▼
  chain from data/llm_tiers.json → LM Studio / Gemini / Ollama / OpenAI URL
```

---

## Known gaps (research targets)

Documented in `docs/AI_HANDLER_FRONTEND.md`:

- Duplicate localStorage keys (`lecture-notes:llm` vs `lecture-notes:llm-tier`)
- Legacy provider/base-url/model UI in `LectureNotesPage` bypasses tier chains
- `corpusClient.generateGroundedNotes()` does not pass `llm_*` from FE
- Coach/agent/classification do not accept FE tier prefs
- `backend/math/ollama_tutor.py` bypasses gateway (not in this bundle)

---

## Out of scope (not exported)

| Path | Reason |
|------|--------|
| `.env` | Contains secrets — use `.env.example` only |
| `data/llm_usage/` | Runtime usage counters |
| `backend/math/ollama_tutor.py` | Separate math stack |
| `transcript-notes-studio/` | Separate desktop app |
| `handoff-export/` | Older snapshots |

---

## Refresh this bundle

From repo root (PowerShell):

```powershell
# Re-run copy script or ask an agent to refresh export-bundle/ai-handler-research/
```

After refresh, zip the folder for Drive upload:

```powershell
Compress-Archive -Path "export-bundle\ai-handler-research\*" -DestinationPath "export-bundle\ai-handler-research.zip" -Force
```

---

## Related live docs (not duplicated elsewhere)

| Doc | Location |
|-----|----------|
| Doc index | `docs/README.md` |
| Architecture summary | `docs/CURRENT_ARCHITECTURE.md` |
| Low-level design | `docs/LLD.md` |
