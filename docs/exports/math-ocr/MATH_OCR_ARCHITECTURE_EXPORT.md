# Math OCR — architecture export

**Exported:** 2026-08-19 · **Updated:** 2026-08-30  
**Audience:** Owner / reviewer — one place for canvas → OCR → tutor → grading.

See **[OCR_CLOSEOUT_2026-08-30.md](./OCR_CLOSEOUT_2026-08-30.md)** for the 2026-08-30 GPU / retrain / calibration work.

Copy on Desktop: `C:\Users\Lenovo\Desktop\math-ocr-export\` (refresh after pull).

---

## 1. What this system does

You draw math on a **grid canvas** (or tldraw in Study Room). The app:

1. **Recognizes** ink → LaTeX (`POST /api/math/ocr`) via TexTeller ONNX + OpenCV.
2. **Detects stuckness** (idle, erasers, optional EEG sim) → **Socratic hint** (`POST /api/math/intervention`).
3. **Grades** typed or recognized answers with **SymPy** (`answer_grade.py` → quiz + vocab practice).
4. **Logs** snapshots + CSV for research (`data_logs/interventions/`, handwriting dataset).
5. **Feeds SRS** when you struggle or confirm/fix LaTeX (`srs_bridge.py` → unified ReviewCards).

**Not the same as:** GRE vocab OCR, lecture notes, or productivity tracking.

---

## 2. North-star loop

```text
Draw on MathGridCanvas
    │
    ├─ Idle OCR (~1.4s debounce, last line band)
    │     POST /api/math/ocr
    │
    ├─ Stuckness (idle ≥45s, erasers, gamma sim)
    │     POST /api/math/intervention
    │         → OCR → hint (rules or Ollama)
    │         → PNG + CSV log
    │         → optional ReviewCard
    │
    ├─ Manual "Ask tutor"
    │     POST /api/math/tutor/hint
    │
    ├─ Training playground (confirm/correct labels)
    │     POST /api/math/train/sample
    │
    └─ Quiz / practice submit
          OCR → gradeable text → SymPy equivalent check
          POST /api/quiz/{id}/answer  OR  /api/vocab/math/practice/submit
```

---

## 3. Architecture (frontend ↔ backend)

```text
┌─────────────────────────────────────────────────────────────────┐
│ FRONTEND (React / Vite)                                         │
├─────────────────────────────────────────────────────────────────┤
│ Pages                                                           │
│   MathPracticePage      — main practice + canvas + intervention │
│   TrainPlaygroundPage   — handwriting training loop             │
│   MathRecognizeTestPage — manual OCR test                       │
│   StudyRoomPage         — tldraw + useStudyRoomOcr              │
│                                                                 │
│ Canvas layer (src/components/math-canvas/)                      │
│   MathGridCanvas        — primary ink grid, exportPng/paths     │
│   TldrawMathCanvas      — Study Room whiteboard                 │
│   useIdleMathOcr        — debounced OCR on last band            │
│   useStrokeAnalytics    — kinematics for backend                │
│   lastBandBbox          — crop region for idle OCR             │
│                                                                 │
│ Orchestration                                                   │
│   StudySessionContext   — stuckness, auto-intervention, SRS     │
│   AITutorIntervention   — hint UI, confirm/fix LaTeX            │
│   MathQuizAnswerPanel   — quiz handwriting → OCR → text answer  │
│   mathClient.ts         — typed API client                      │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP JSON + base64 PNG
                             │ paths_json, stroke_metrics_json
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ BACKEND (FastAPI)  prefix /api/math                             │
├─────────────────────────────────────────────────────────────────┤
│ router.py              — all math routes                        │
│ ocr_service.py           — PNG → LaTeX pipeline (core)            │
│   ├─ texteller_onnx.py   — TexTeller 3 ONNX (CPU)               │
│   ├─ mfd_onnx.py         — formula box detection                │
│   ├─ line_detect.py      — multi-line bands                     │
│   ├─ structure_verify.py — stroke bbox vs LaTeX confidence      │
│   └─ stroke_symbol.py    — glyph disambiguation                 │
│ intervention_handler.py — stuckness + OCR + hint                │
│ intervention_log.py      — PNG snapshots + DSC CSV              │
│ rule_tutor.py / ollama_tutor.py — Socratic hints                │
│ answer_grade.py          — SymPy answer equivalence             │
│ eval_service.py          — SymPy calculator widget              │
│ srs_bridge.py            — intervention → ReviewCard            │
│ training_service.py + training_log.py — dataset + curriculum  │
│ skills.py + generators/layer0.py — procedural drills            │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ DATA / ARTIFACTS                                                │
│   data_logs/interventions/{id}.png                              │
│   data_logs/DSC_interventions_{date}.csv                        │
│   data_logs/DSC_handwriting_dataset.csv                         │
│   data_logs/DSC_Kinematics.csv (when metrics sent)              │
│   SQLite: math questions, ReviewCards, attempts                  │
└─────────────────────────────────────────────────────────────────┘
```

**Mount point:** `backend/main.py` includes math router at `/api/math`.

---

## 4. OCR pipeline (backend detail)

`ocr_service.recognize_canvas()` — simplified steps:

| Step | What |
|------|------|
| 1 | Decode base64 PNG; optional crop from `crop_bbox` or stroke paths |
| 2 | OpenCV: mask ink, CLAHE, content crop |
| 3 | **line_detect:** split into horizontal bands (stroke / projection / MFD) |
| 4 | **texteller_onnx:** each band → LaTeX string |
| 5 | **structure_verify:** compare stroke geometry to LaTeX → `structural_confidence` |
| 6 | **SymPy** `latex_is_complete` → `incomplete_step` flag |
| 7 | Fallbacks (tiered): per-cell OCR, contour digit, Ollama vision, NIM teacher |

**Response shape (`POST /api/math/ocr`):**  
`latex`, `lines[]`, `confidence`, `structural_confidence`, `incomplete_step`, optional `crop_bbox`, `engine`.

**Status:** `GET /api/math/ocr/status` — TexTeller loaded?, Ollama vision?, NIM?

**Deps:** `backend/requirements-ocr.txt` — onnxruntime, optimum, transformers, opencv.  
**Not used:** full Pix2Text pip package (MFD ONNX only).

---

## 5. Frontend routes (user-facing)

| Route | Page | Canvas |
|-------|------|--------|
| `/math-tutor` | Dashboard | — |
| `/math-tutor/practice/:topicId` | MathPracticePage | MathGridCanvas |
| `/math-tutor/train` | TrainPlaygroundPage | MathGridCanvas |
| `/math-tutor/recognize-test` | MathRecognizeTestPage | MathGridCanvas |
| Study Room | StudyRoomPage | TldrawMathCanvas |

Plugin: `src/plugins/math_tutor_plugin.tsx`

**Legacy (superseded):** `MathSplitWhiteboard.tsx`, `MathWhiteboard.tsx` — old react-sketch-canvas; practice uses **MathGridCanvas**.

---

## 6. API routes (complete list)

### `/api/math/*`

| Method | Path | Role |
|--------|------|------|
| GET | `/skills` | Layer-0 skill tree |
| GET | `/ocr/status` | Engine availability + `execution_provider` (CUDA/CPU) |
| POST | `/ocr` | Canvas → LaTeX |
| POST | `/intervention` | Stuckness → hint + log |
| PATCH | `/intervention/{id}/recover` | Dismissed / recovered |
| PATCH | `/intervention/{id}/correct` | Human fix LaTeX → dataset + SRS |
| POST | `/tutor/hint` | Manual Ask tutor |
| POST | `/eval` | SymPy calculator |
| GET | `/train/curriculum` | Training prompts |
| GET | `/train/progress` | User stats |
| POST | `/train/sample` | Confirm/correct handwriting |
| POST | `/train/retrain` | Export CSV → TexTeller `formulas.jsonl`; optional `--mode train` |
| POST | `/train/retrain-stroke-symbol` | Real-ink stroke disambiguator retrain |
| POST | `/train/recalibrate-structure` | Tune `structure_verify` thresholds |
| GET/POST | `/questions/*` | Question bank import/list |

### Grading (uses same SymPy layer)

| Path | Role |
|------|------|
| `POST /api/quiz/{id}/answer` | Unified quiz, domain=math |
| `POST /api/vocab/math/practice/submit` | Legacy practice submit |

---

## 7. Stuckness & tutor silence

**Stuckness (shipped):**

```text
stuckness = 0.4·min(idle/90,1) + 0.3·min(erasers/5,1) + 0.3·min((gamma-55)/30,1)
fire when stuckness > 0.5 AND idle ≥ 45s AND cooldown ≥ 120s
```

**Tutor silence:** low OCR or structural confidence → suppress auto-interrupt; user can confirm/fix in `AITutorIntervention`.

**Optional LLM:** `OLLAMA_ENABLED=1`, `OLLAMA_VISION_MODEL` for incomplete steps. Default = rule-based hints.

---

## 8. Shipped vs deferred

### Shipped (scaffold works end-to-end)

| Area | Notes |
|------|--------|
| MathGridCanvas + idle OCR | Primary UX |
| TexTeller ONNX multi-line | CPU path; **CUDA auto** since 2026-08-30 |
| Intervention + DSC logs | PNG + CSV |
| SymPy grading | Quiz + practice |
| SRS bridge | struggle / recover / correct |
| Training playground + retrain export | Dataset CSV → TexTeller layout (**2026-08-30**) |
| Stroke-symbol real-ink retrain | `stroke_symbol_model.npz` (**2026-08-30**) |
| Structure verify calibration | `structure_thresholds.json` (**2026-08-30**) |
| Study Room tldraw OCR | `useStudyRoomOcr` |
| NIM teacher labels | Opt-in `NIM_API_KEY` |

### Deferred / not in completion mandate

| Item | Notes |
|------|--------|
| **Production OCR accuracy** | `CANVAS_OCR_ROADMAP`: quality not production-ready |
| **Phase 3c as sprint goal** | AGENTS.md: not required for study completion |
| **Fine-tune TexTeller weights** | Export wired; ONNX swap after train still manual |
| **CPU-only ONNX** | ~~Removed 2026-08-30~~ — use `onnxruntime-gpu` + `OCR_ONNX_DEVICE=auto` |
| **WebGazer gaze** | Research only |
| **Real EEG in stuckness** | Simulated in frontend today |
| **Full Pix2Text package** | MFD ONNX subset only |
| **Mathpix / cloud OCR default** | Local-first policy |

---

## 9. How to run / verify

```bat
run.bat
scripts\install_ocr.bat
scripts\download_texteller.bat
```

| Check | Where |
|-------|--------|
| OCR status | `GET http://localhost:8000/api/math/ocr/status` |
| Manual test UI | `/math-tutor/recognize-test` |
| Practice + intervention | `/math-tutor/practice/{topicId}` |
| Pytest | `pytest tests/test_math_ocr.py tests/test_intervention_handler.py tests/test_math_quiz_multi.py -q` |

---

## 10. File count summary

| Layer | ~Files |
|-------|--------|
| Frontend canvas + pages | 18 |
| Frontend API/context/widgets | 8 |
| Backend math/ | 16 |
| Backend quiz integration | 2 |
| Tests | 10 |
| Scripts + OCR deps | 8 |
| Docs (canonical) | 6+ |
| **Total related** | **~55–60** |

Full paths: **[FILE_INDEX.md](./FILE_INDEX.md)**

---

## 11. One paragraph summary

CALT’s math OCR path is a **local-first vision stack**: you draw on **MathGridCanvas**, the frontend sends PNG + stroke paths to **`/api/math/ocr`**, the backend runs **OpenCV + TexTeller ONNX** to produce LaTeX with confidence and incomplete-step flags, and **SymPy** validates answers in quiz and practice. When you’re stuck, **stuckness heuristics** trigger **`/api/math/intervention`**, which logs snapshots and may show a **Socratic hint** (rules or optional Ollama) and update **ReviewCards**. Training and Study Room reuse the same OCR core; **production accuracy and multimodal gaze/EEG** remain future work.
