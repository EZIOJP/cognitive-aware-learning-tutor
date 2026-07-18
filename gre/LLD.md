# LLD — GRE vocab + math practice + OCR

Low-level design for implementers and LLD reviewers. Paths are repo-relative.

---

## 0. Startup order

```text
backend/main.py
  → Alembic migrations
  → seed vocab / math templates if empty
  → mount routers: vocab, math, quiz, hub, …
```

Production entry: **`backend/main.py`**.  
Do not extend `backend/vocab_backend.py` (legacy uvicorn shim).

---

## 1. Module map

### Vocab

| Module | Role |
|--------|------|
| `backend/vocab/router.py` | Mount / prefix |
| `backend/vocab/routes.py` | Auth, groups, progress, adaptive quiz HTTP |
| `backend/vocab/quiz_store.py` | Adaptive session store |
| `backend/vocab/repository.py` | DB access |
| `backend/vocab/words.py` | Word helpers |
| `backend/vocab/hub_hooks.py` | Hub event emission |
| `backend/vocab/enrich.py` | Optional enrichment |
| `backend/vocab/gref_import.py` | Import helpers |

### Math

| Module | Role |
|--------|------|
| `backend/math/router.py` | All `/api/math` HTTP |
| `backend/math/rule_tutor.py` | Default hints |
| `backend/math/ollama_tutor.py` | LLM hints |
| `backend/math/ocr_service.py` | Preprocess + tier orchestration |
| `backend/math/texteller_onnx.py` | TexTeller ONNX |
| `backend/math/intervention_handler.py` | Stuckness → OCR → hint + Socratic guard |
| `backend/math/intervention_log.py` | DSC CSV + PNG paths |
| `backend/math/training_service.py` | Train curriculum / samples |
| `backend/math/training_log.py` | Handwriting + kinematics CSV |
| `backend/math/eval_service.py` | Answer eval |
| `backend/math/schemas.py` | Pydantic I/O |
| `backend/math/services/import_questions.py` | Question import |
| `backend/math/services/randomizer.py` | Drill randomizer |

### Frontend anchors

| Area | Path |
|------|------|
| Vocab cycle | `src/features/vocab/cycle/components/CycleManager.tsx` |
| Vocab read | `src/features/vocab/components/read/ReadMode.tsx` |
| Vocab store (guest) | `src/features/vocab/store/vocabStore.ts` |
| Practice | `src/pages/math/MathPracticePage.tsx` |
| Train | `src/pages/math/TrainPlaygroundPage.tsx` |
| Recognize | `src/pages/math/MathRecognizeTestPage.tsx` |
| Session / stuckness | `src/context/StudySessionContext.tsx` |
| Whiteboard | `src/app/components/MathSplitWhiteboard.tsx` |
| Grid canvas (OCR) | MathGridCanvas (math pages) |
| Math client | `src/api/mathClient.ts` (or equivalent under `src/`) |
| Config | `src/config.ts` |

---

## 2. Data model (SQLite — relevant tables)

DB: `data/vocab_app.db`

| Model / table | Use |
|---------------|-----|
| Users + JWT auth | Vocab login |
| Words / groups | GRE list |
| `word_progress` | Per-user mastery, times_asked, due |
| `quiz_sessions` | Vocab adaptive (+ may share name with global) |
| `math_question_templates` | Template drills |
| `math_questions` | Imported bank |
| `math_attempts` | Practice attempts |

Filesystem (math OCR / research):

| Path | Use |
|------|-----|
| `data_logs/interventions/{id}.png` | Intervention snapshots |
| `data_logs/DSC_interventions_*.csv` | Intervention index |
| `data_logs/DSC_handwriting_dataset.csv` | Train / correct labels |
| `data_logs/DSC_Kinematics.csv` | Per-stroke metrics |

Static bootstrap: `public/data/words.json`.

---

## 3. Vocab — call graphs

### 3.1 Auth

```text
POST /api/vocab/auth/register
POST /api/vocab/auth/login     → JWT
GET  /api/vocab/auth/me
```

Frontend: `authClient.ts` + `AuthContext.tsx` → `vocab:auth-token`.

### 3.2 Hub + read

```text
GET /api/vocab/groups/detailed/     → group stats (notStarted = times_asked === 0)
GET /api/vocab/words/by-criteria/   → filters: group, mastery_min/max, due_for_review, word_ids
POST /api/vocab/progress/{id}/read  → mark read / swipe
PATCH /api/vocab/progress/{word_id} → update progress fields
GET /api/vocab/progress/summary     → hub + cycle metadata
GET /api/vocab/quiz/dashboard/      → cycle dashboard
```

### 3.3 Adaptive quiz (cycle only)

```text
POST /api/vocab/quiz/adaptive/start/
GET  /api/vocab/quiz/adaptive/{session_id}/question/
POST /api/vocab/quiz/adaptive/{session_id}/answer/
POST /api/vocab/quiz/adaptive/{session_id}/complete/
```

Store: `quiz_store.py`. UI sequence: `CycleReadStep` → `CycleQuizStep` → `CycleReportStep` → `LowMasteryPrompt`.

### 3.4 Guest fallback

```text
No JWT
  → ReadMode / cycleService uses vocabStore + words.json
  → Progress stays in localStorage
```

---

## 4. Math practice — call graphs

### 4.1 Question bank

```text
POST /api/math/questions/import/json
POST /api/math/questions/import/file
POST /api/math/questions/import/preview
GET  /api/math/questions/export/json
GET  /api/math/questions
DELETE /api/math/questions/{question_id}
```

### 4.2 Manual tutor hint

```text
MathPracticePage
  → export context / problem text
  → POST /api/math/tutor/hint
       → if ollama_enabled: ollama_tutor
       → else: rule_tutor
  → show hint UI
```

### 4.3 Eval

```text
POST /api/math/eval
```

---

## 5. Math OCR — tiers and call graph

### 5.1 Status + recognize

```text
GET  /api/math/ocr/status   → which tiers available
POST /api/math/ocr          → image (+ optional paths_json) → MathOcrOut
```

Typical pipeline inside `ocr_service.py`:

```text
PNG bytes
  → grayscale / morph / connected components (OpenCV)
  → optional mask_from_paths(paths_json)
  → crop regions
  → Tier: TexTeller ONNX
  → if incomplete / hallucinated:
       → optional Ollama vision (OLLAMA_VISION_MODEL)
       → optional NIM teacher (NIM_API_KEY)
  → SymPy / latex guards (_ocr_looks_hallucinated)
  → optional per-cell OCR rescue (train grid cells)
  → { latex, confidence, incomplete_step, tier, … }
```

### 5.2 Intervention

```text
StudySessionContext stuckness
  → MathPracticePage / AITutorIntervention
  → POST /api/math/intervention
       → intervention_handler
            → OCR
            → tutor hint + Socratic check
            → intervention_log (PNG + CSV)
  → PATCH /api/math/intervention/{snapshot_id}/recover
  → PATCH /api/math/intervention/{snapshot_id}/correct   → handwriting dataset
```

### 5.3 Stuckness heuristic (v1)

```text
stuckness = 0.4·min(idle/90,1)
          + 0.3·min(erasers/5,1)
          + 0.3·min((gamma-55)/30,1)

fire when stuckness > 0.5
     and idle ≥ 45s
     and cooldown ≥ 120s
```

Config gates: `config.intervention.enabled`, `config.intervention.autoTrigger`.  
EEG: `config.dev.useSimulatedData` default true.

### 5.4 Train playground

```text
GET  /api/math/train/curriculum
GET  /api/math/train/progress
POST /api/math/train/sample      → log PNG + metrics + target_latex
POST /api/math/train/retrain     → optional retrain hook
```

UI: `TrainPlaygroundPage` + stroke analytics (`useStrokeAnalytics` / `strokeMetrics`).

---

## 6. Frontend cognitive load wiring

| Key (`src/config.ts`) | Default | Meaning |
|-----------------------|---------|---------|
| `cognitiveLoad.highThreshold` | 60 | High load badge |
| `cognitiveLoad.mediumThreshold` | 35 | Medium |
| `dev.useSimulatedData` | true | Sim EEG |
| `intervention.enabled` | true | Show intervention UI |
| `intervention.autoTrigger` | true | Auto fire vs manual |

Context: `StudySessionContext.tsx` — idle, eraser counts, canvas handle (`exportPng`, `exportPaths`, `getEraserEventCount`).

---

## 7. API quick reference

### Vocab (`/api/vocab`)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/auth/login` | JWT |
| POST | `/auth/register` | Register |
| GET | `/auth/me` | Current user |
| GET | `/groups/detailed/` | Groups + progress |
| GET | `/words/by-criteria/` | Filtered word list |
| POST | `/progress/{id}/read` | Read mark |
| GET | `/progress/summary` | Aggregates |
| GET | `/quiz/dashboard/` | Cycle dashboard |
| POST | `/quiz/adaptive/start/` | Start cycle quiz |
| GET | `/quiz/adaptive/{id}/question/` | Next Q |
| POST | `/quiz/adaptive/{id}/answer/` | Answer |
| POST | `/quiz/adaptive/{id}/complete/` | Finish |
| * | `/admin/...` | Admin reset / word CRUD / export |

### Math (`/api/math`)

| Method | Path | Purpose |
|--------|------|---------|
| * | `/questions/...` | Import / list / delete |
| POST | `/tutor/hint` | Manual tutor |
| POST | `/eval` | Score answer |
| GET | `/ocr/status` | OCR readiness |
| POST | `/ocr` | Image → LaTeX |
| POST | `/intervention` | Stuckness pipeline |
| PATCH | `/intervention/{id}/recover` | Dismiss / recovered |
| PATCH | `/intervention/{id}/correct` | Human LaTeX label |
| * | `/train/...` | Curriculum + samples |

---

## 8. Env / deps (math OCR)

```text
OLLAMA_ENABLED=0|1
OLLAMA_VISION_MODEL=...
NIM_API_KEY=...                 # optional

# Python extras (scripts/install_ocr.bat)
opencv-python-headless
onnxruntime + optimum + transformers
sympy
```

Note: `opencv-python` (GUI) vs `opencv-python-headless` can conflict with `face_tracker` — prefer headless for OCR server path.

---

## 9. Do-not-touch / dual-path rules

| Rule | Detail |
|------|--------|
| No `UniversalReadMode.jsx` | Use `ReadMode.tsx` |
| No `vocab_backend.py` features | Mount via `main.py` |
| Cycle quiz ≠ global quiz | `/api/vocab/quiz/adaptive/*` vs `/api/quiz/*` |
| Guest ≠ server progress | No silent merge |
| Do not stack 7B models | One math LLM with `keep_alive` during session |

---

## 10. Verify (smoke)

```bat
run.bat
```

1. Login `admin` / `admin123` → `/gre-vocab` loads groups  
2. `/gre-vocab/cycle` — one group read → quiz → report  
3. `/math-tutor/practice/...` — Ask tutor returns a hint  
4. `/math-tutor/train` — draw `3` → Recognize → sensible LaTeX  
5. Optional: wait for stuckness / enable autoTrigger → intervention log row appears  

---

## 11. Related live docs

- `docs/GRE_VOCAB_PHASE1.md`
- `docs/MATH_TUTOR_VISION_PIPELINE.md`
- `docs/CANVAS_OCR_ROADMAP.md`
- `docs/FILE_MAP.md`
- `docs/MATH_QUESTION_IMPORT.md`
- `docs/CENTRAL_HUB.md`
