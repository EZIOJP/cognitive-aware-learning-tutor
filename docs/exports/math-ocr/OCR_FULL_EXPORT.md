# Math OCR — Full Export (Backend · Frontend · Architecture · Plan · Build)

**Updated:** 2026-08-30  
**Repo:** Cognitive-Aware Learning Tutor  
**Audience:** Owner / developer — single reference for the handwriting math OCR system.

**Related docs in this folder:**

| Doc | Purpose |
|-----|---------|
| [MATH_OCR_BUILD_AND_CHANGES.md](./MATH_OCR_BUILD_AND_CHANGES.md) | Step-by-step install + retrain |
| [MATH_OCR_ARCHITECTURE_EXPORT.md](./MATH_OCR_ARCHITECTURE_EXPORT.md) | Original architecture (pre-UniMERNet) |
| [OCR_RECOGNITION_ROADMAP.md](./OCR_RECOGNITION_ROADMAP.md) | Phases A–E shipped; F deferred |
| [OCR_TRAINING_DATA_POLICY.md](./OCR_TRAINING_DATA_POLICY.md) | Editable vs permanent samples |
| [OCR_CLOSEOUT_2026-08-30.md](./OCR_CLOSEOUT_2026-08-30.md) | GPU / retrain close-out |
| [FILE_INDEX.md](./FILE_INDEX.md) | File-by-file index |

---

## 1. What the system does

You draw math on a **grid canvas**. The app:

1. **Recognizes** ink → LaTeX (`POST /api/math/ocr`)
2. **Reviews** low-confidence output (confirm gate before quiz submit)
3. **Grades** with SymPy (`answer_grade.py`)
4. **Hints** when stuck (`POST /api/math/intervention`)
5. **Learns** from your corrections (`POST /api/math/train/sample`)
6. **Feeds SRS** on struggle (`srs_bridge.py` → ReviewCards)

**Engines (2026-08-30):** TexTeller 3 ONNX + optional **UniMERNet-T ONNX** dual-engine with SymPy repair loop.

---

## 2. Architecture diagram

```text
┌──────────────────────────────────────────────────────────────────────────┐
│ FRONTEND (React 18 · Vite · TypeScript)                                  │
├──────────────────────────────────────────────────────────────────────────┤
│ Pages                                                                    │
│   /math-tutor/practice/:id     MathPracticePage                          │
│   /math-tutor/train            TrainPlaygroundPage                       │
│   /math-tutor/recognize-test   MathRecognizeTestPage                     │
│   /math-tutor/training-data    OcrTrainingDataPage                       │
│   Study Room                   StudyRoomPage (tldraw)                      │
│   Quiz                         MathQuizAnswerPanel + GlobalQuizRunner    │
│                                                                          │
│ Canvas (src/components/math-canvas/)                                     │
│   MathGridCanvas        Primary ink grid · exportPng · exportPaths       │
│   TldrawMathCanvas      Study Room whiteboard                            │
│   useIdleMathOcr        1.4s debounce · last band crop · postMathOcr     │
│   useStrokeAnalytics    Kinematics → stroke_metrics_json                 │
│   OcrReviewPanel        Per-line edit · confirm gate · provider badge    │
│   lastBandBbox          Crop region for idle OCR                         │
│                                                                          │
│ API client: src/api/mathClient.ts                                        │
│ Context:    StudySessionContext (stuckness · intervention)               │
└───────────────────────────────┬──────────────────────────────────────────┘
                                │ JSON + base64 PNG
                                │ paths_json · stroke_metrics_json · crop_bbox
                                ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ BACKEND (FastAPI)  /api/math                                             │
├──────────────────────────────────────────────────────────────────────────┤
│ router.py                    All math routes                             │
│                                                                          │
│ OCR core                                                                 │
│   ocr_service.py             recognize_canvas · recognize_multiline      │
│   ocr_engine.py              Dual-engine: TexTeller + UniMERNet          │
│   texteller_onnx.py          TexTeller 3 ONNX (primary)                  │
│   unimernet_onnx.py          UniMERNet-T ONNX (optional second)          │
│   pure_onnx_unimernet.py     Vendored inference (torvexlabs)             │
│   onnx_providers.py          CUDA → CPU provider selection               │
│   line_detect.py             Multi-line band detection                   │
│   mfd_onnx.py                Formula box detection (band upgrade)        │
│                                                                          │
│ Post-OCR intelligence                                                    │
│   stroke_symbol.py           Glyph disambiguation · ensemble vote        │
│   structure_verify.py        Stroke geometry vs LaTeX                    │
│   structure_learned.py       MLP verifier boost                          │
│   structure_calibrate.py     Threshold tuning from samples                 │
│   structure_misseg_log.py    Fraction mis-segmentation log               │
│   sympy_repair.py            SymPy parse fail → alternate engine         │
│   latex_repair.py            Deterministic LaTeX micro-fixes             │
│   latex_validate.py          Bracket / frac validators (TAMER-lite)      │
│   stroke_order.py            Top-to-bottom stroke normalization          │
│                                                                          │
│ Training & models                                                        │
│   training_log.py            CSV + PNG + paths_json dataset              │
│   training_service.py        Curriculum tiers / prompts                  │
│   mathwriting_import.py      Bulk MathWriting InkML import               │
│   retrain_service.py         TexTeller fine-tune export                  │
│                                                                          │
│ Tutor · grade · SRS                                                      │
│   intervention_handler.py    Stuckness → OCR → hint                      │
│   answer_grade.py            SymPy equivalence                           │
│   srs_bridge.py              Intervention → ReviewCard                   │
└───────────────────────────────┬──────────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ DATA & ARTIFACTS                                                         │
├──────────────────────────────────────────────────────────────────────────┤
│ data/math/unimernet/artifacts/     encoder/decoder ONNX (~755 MB)        │
│ data/math/unimernet/models/        tokenizer + unimernet_tiny.pth        │
│ data/math/stroke_symbol_model.npz  Glyph classifier                     │
│ data/math/structure_thresholds.json  Calibrated geometry thresholds      │
│ data/math/texteller_finetune/      TexTeller export layout               │
│ data_logs/DSC_handwriting_dataset.csv  Confirmed training samples          │
│ data_logs/interventions/           PNG snapshots                         │
│ HF cache / TEXTELLER_CACHE_DIR     TexTeller weights (~1 GB)             │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 3. OCR pipeline (request flow)

```text
POST /api/math/ocr
  │
  ├─ decode base64 PNG
  ├─ stroke_order.normalize_paths_json_stroke_order (Phase 3)
  ├─ synthesize from paths if transparent export empty
  ├─ crop_to_content / apply_crop_bbox (idle last-band)
  │
  ├─ line_detect.detect_line_bands (stroke metrics or projection)
  │     └─ if ≥2 bands → per-band loop
  │
  ├─ ocr_engine.recognize_crop (each band)
  │     ├─ texteller_onnx.recognize_image (prepared crop)
  │     ├─ unimernet_onnx.recognize_image (raw crop)  [if installed]
  │     ├─ ensemble boost if both agree
  │     └─ sympy_repair.apply_repair_pipeline
  │           ├─ latex_repair rules
  │           └─ alternate engine if SymPy parse fails
  │
  ├─ stroke_symbol.maybe_disambiguate_latex (short glyphs)
  ├─ structure_verify.verify_structure (geometry + MLP)
  │
  ├─ fallbacks if empty/hallucinated:
  │     per-cell OCR · contour digits · Ollama vision · NIM teacher
  │
  └─ MathOcrOut: latex, lines[], confidence, structural_confidence,
                 incomplete_step, needs_review, tier
```

---

## 4. Backend — file map

| File | Role |
|------|------|
| `backend/math/router.py` | HTTP routes |
| `backend/math/ocr_service.py` | Main OCR orchestration |
| `backend/math/ocr_engine.py` | Dual-engine + repair |
| `backend/math/texteller_onnx.py` | TexTeller 3 ONNX |
| `backend/math/unimernet_onnx.py` | UniMERNet-T wrapper |
| `backend/math/pure_onnx_unimernet.py` | Pure ONNX runtime (vendored) |
| `backend/math/onnx_providers.py` | CUDA/CPU providers |
| `backend/math/line_detect.py` | Line band detection |
| `backend/math/mfd_onnx.py` | Formula detection ONNX |
| `backend/math/stroke_symbol.py` | Glyph ensemble |
| `backend/math/structure_verify.py` | Structure confidence |
| `backend/math/structure_learned.py` | MLP verifier |
| `backend/math/structure_calibrate.py` | Calibrate thresholds |
| `backend/math/sympy_repair.py` | Re-OCR repair loop |
| `backend/math/latex_repair.py` | LaTeX rule fixes |
| `backend/math/latex_validate.py` | Bracket validators |
| `backend/math/stroke_order.py` | Stroke sort |
| `backend/math/training_log.py` | Dataset CRUD |
| `backend/math/retrain_service.py` | TexTeller export |
| `backend/math/mathwriting_import.py` | Bulk import |
| `backend/requirements-ocr.txt` | OCR pip deps |

---

## 5. Backend — API reference

### 5.1 OCR

| Method | Path | Body / query | Response |
|--------|------|--------------|----------|
| GET | `/api/math/ocr/status` | — | `texteller_available`, `unimernet_available`, `engines[]`, `execution_provider`, `primary_engine`, `finetuned_model` |
| POST | `/api/math/ocr` | `canvas_image`, `paths_json?`, `stroke_metrics_json?`, `crop_bbox?`, `multiline?` | `latex`, `lines[]`, `confidence`, `structural_confidence`, `incomplete_step`, `needs_review`, `tier` |

### 5.2 Training

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/math/train/sample` | Save confirmed/corrected sample |
| GET | `/api/math/train/samples` | List samples (`has_paths_json` filter) |
| GET | `/api/math/train/samples/{id}` | Single sample |
| GET | `/api/math/train/samples/{id}/image` | PNG crop |
| POST | `/api/math/train/import` | MathWriting bulk import |
| GET | `/api/math/train/duplicates` | Duplicate keys |
| POST | `/api/math/train/duplicates/cleanup` | Remove dupes |
| POST | `/api/math/train/retrain` | TexTeller export (`mode=export\|train`) |
| POST | `/api/math/train/retrain-stroke-symbol` | Retrain glyph classifier |
| POST | `/api/math/train/recalibrate-structure` | Calibrate geometry |
| POST | `/api/math/train/reload-model` | Hot-swap TexTeller ONNX (admin) |
| GET | `/api/math/train/curriculum` | Training tiers |
| GET | `/api/math/train/progress` | Tier progress |

### 5.3 Related (not OCR but same canvas loop)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/math/intervention` | Stuckness → hint |
| POST | `/api/math/tutor/hint` | Manual Socratic hint |
| POST | `/api/quiz/{id}/answer` | Quiz submit (uses OCR from FE) |

---

## 6. Frontend — file map

| File | Role |
|------|------|
| `src/api/mathClient.ts` | Typed API · `postMathOcr`, `fetchOcrStatus`, training APIs |
| `src/components/math-canvas/MathGridCanvas.tsx` | Primary canvas |
| `src/components/math-canvas/TldrawMathCanvas.tsx` | Study Room canvas |
| `src/components/math-canvas/useIdleMathOcr.ts` | Debounced background OCR |
| `src/components/math-canvas/useStrokeAnalytics.ts` | Stroke kinematics |
| `src/components/math-canvas/OcrReviewPanel.tsx` | Review UI + confirm gate |
| `src/components/math-canvas/lastBandBbox.ts` | Last line crop bbox |
| `src/components/math-canvas/strokeMetrics.ts` | Metrics + coalesce |
| `src/pages/math/MathPracticePage.tsx` | Practice + save to training |
| `src/pages/math/TrainPlaygroundPage.tsx` | Labeling loop |
| `src/pages/math/MathRecognizeTestPage.tsx` | Manual OCR test |
| `src/pages/math/OcrTrainingDataPage.tsx` | Dataset manager |
| `src/features/quiz/MathQuizAnswerPanel.tsx` | Quiz handwriting + gate |
| `src/features/quiz/GlobalQuizRunner.tsx` | Quiz runner confirm gate |
| `src/study-room/hooks/useStudyRoomOcr.ts` | Study Room OCR hook |
| `src/context/StudySessionContext.tsx` | Stuckness + intervention |

---

## 7. Frontend — user routes

| URL | Page | OCR behavior |
|-----|------|--------------|
| `/math-tutor/practice/:topicId` | MathPracticePage | Idle OCR · review panel · save training |
| `/math-tutor/train` | TrainPlaygroundPage | Confirm/correct labels → dataset |
| `/math-tutor/recognize-test` | MathRecognizeTestPage | Manual full-canvas OCR test |
| `/math-tutor/training-data` | OcrTrainingDataPage | Import · dupes · retrain buttons |
| `/review` (math quiz) | MathQuizAnswerPanel | OCR → confirm → submit blocked until OK |
| Study Room | StudyRoomPage | tldraw + useStudyRoomOcr |

### Confirm gate rules (`OcrReviewPanel`)

Submit blocked when any of:

- `confidence < 0.55`
- `structural_confidence < 0.45`
- `needs_review === true`
- `incomplete_step === true`

User must click **Confirm** after editing LaTeX.

---

## 8. Environment variables

| Variable | Values | Default | Effect |
|----------|--------|---------|--------|
| `OCR_ONNX_DEVICE` | `auto`, `cuda`, `cpu` | `auto` | ONNX execution provider |
| `OCR_PRIMARY_ENGINE` | `auto`, `texteller`, `unimernet` | `auto` | Which engine wins on disagreement |
| `TEXTELLER_MODEL_ID` | HF model id | `Ji-Ha/TexTeller3-ONNX-dynamic` | TexTeller weights |
| `TEXTELLER_FINETUNED_MODEL` | HF path or id | — | Hot-swappable fine-tuned model |
| `TEXTELLER_CACHE_DIR` | path | HF default | Weight cache |
| `UNIMERNET_ARTIFACTS_DIR` | path | `data/math/unimernet/artifacts` | ONNX files |
| `UNIMERNET_TOKENIZER_DIR` | path | `data/math/unimernet/models/unimernet_tiny` | Tokenizer |
| `UNIMERNET_PURE_MODULE` | path | — | Override pure_onnx path |
| `OLLAMA_VISION_MODEL` | model name | — | Tier-2 vision fallback |
| `NIM_API_KEY` | key | — | NIM teacher tier-0 |

---

## 9. Plan & roadmap status

### Shipped (Phases A–E + Gemini 3-phase)

| Phase | Deliverable | Status |
|-------|-------------|--------|
| A | GPU ONNX, training UI, stroke retrain, structure calibrate | ✅ |
| B | MathWriting import, duplicates, paths filter | ✅ |
| C | OcrReviewPanel, quiz confirm gate, provider badge | ✅ |
| D | TexTeller hot-swap, ensemble, NIM auto-confirm | ✅ |
| E | MLP verifier, matrix detect, misseg log | ✅ |
| Gemini 1 | UniMERNet-T optional second ONNX backend | ✅ |
| Gemini 2 | SymPy-triggered re-OCR repair loop | ✅ |
| Gemini 3 | Bracket validator, LaTeX repair, CDM eval, stroke order | ✅ |

### Remaining (quality, not architecture)

| Item | How |
|------|-----|
| Personal handwriting accuracy | Confirm/correct 50+ samples → retrain |
| TexTeller fine-tune on your ink | `POST /train/retrain?mode=export` then train |
| CDM benchmark baseline | `python scripts/eval_ocr_cdm.py export.csv` |
| GPU speed | `pip install onnxruntime-gpu` |
| Docs sync | PROJECT_STATUS date |

### Explicitly deferred (Phase F)

- WebGazer gaze in stuckness
- Real EEG hardware
- Pix2Text full package
- Mathpix cloud default

---

## 10. How to build & run

### 10.1 Whole app (first time)

```bat
run.bat
```

- Frontend: http://localhost:5173  
- API: http://localhost:8000  
- Health: http://localhost:8000/health  

### 10.2 OCR stack (TexTeller)

```bat
scripts\install_ocr.bat
```

Installs `backend/requirements-ocr.txt`. First OCR request downloads ~1 GB TexTeller weights.

### 10.3 UniMERNet second engine (one-time)

```bat
scripts\install_unimernet.bat
```

This script:

1. Installs `tokenizers`, `ftfy`, `huggingface_hub`
2. Downloads `pure_onnx_unimernet.py`
3. Downloads tokenizer from GitHub
4. Downloads `unimernet_tiny.pth` from public HF (`wanderkid/unimernet_tiny`)
5. Converts to ONNX via `scripts/convert_unimernet_onnx.py` (~755 MB artifacts)

**Verify:**

```http
GET http://localhost:8000/api/math/ocr/status
```

Expect: `"engines": ["texteller", "unimernet"]`, `"tier": "dual"`.

### 10.4 GPU (optional, faster)

```bat
pip uninstall onnxruntime -y
pip install onnxruntime-gpu
set OCR_ONNX_DEVICE=auto
```

Restart API. Status should show `CUDAExecutionProvider` after first OCR.

### 10.5 Improve accuracy (operator loop)

```text
1. Draw in Train Playground → confirm/correct → save sample
2. Repeat 10–20 times
3. scripts\retrain_stroke_symbol.bat
4. scripts\recalibrate_structure.bat
5. (50+ samples) POST /api/math/train/retrain?mode=export
6. Optional: fine-tune TexTeller externally, set TEXTELLER_FINETUNED_MODEL
7. POST /api/math/train/reload-model
8. Benchmark: python scripts\eval_ocr_cdm.py your_export.csv
```

---

## 11. Scripts reference

| Script | Purpose |
|--------|---------|
| `scripts/install_ocr.bat` | TexTeller deps |
| `scripts/install_unimernet.bat` | Full UniMERNet auto-install |
| `scripts/install_unimernet.py` | Python installer (called by bat) |
| `scripts/convert_unimernet_onnx.py` | .pth → ONNX export |
| `scripts/retrain_stroke_symbol.bat` | Glyph classifier retrain |
| `scripts/recalibrate_structure.bat` | Geometry thresholds |
| `scripts/retrain_texteller.bat` | TexTeller export |
| `scripts/eval_ocr_cdm.py` | CDM-lite offline eval |

---

## 12. Tests

```bat
python -m pytest tests/test_math_ocr.py tests/test_math_ocr_phases.py -q
```

- No model download required for unit tests
- Integration tests skip if TexTeller/UniMERNet artifacts missing

---

## 13. Success metrics (targets)

| Metric | Target |
|--------|--------|
| Single-digit / operator accuracy (your ink) | >95% after stroke retrain |
| Confirm without edit rate | >80% on curriculum prompts |
| Multi-line fraction structure agree | >70% |
| OCR p50 latency (GPU) | <1.0s per line |
| Tutor false interrupt rate | ↓ via structure calibration |

---

## 14. Quick troubleshooting

| Symptom | Fix |
|---------|-----|
| OCR offline badge | Run `scripts\install_ocr.bat` |
| No UniMERNet badge | Run `scripts\install_unimernet.bat` |
| Slow OCR | Install `onnxruntime-gpu` |
| Hallucinated LaTeX (tables, `\mathbb`) | `_ocr_looks_hallucinated` rejects; try per-cell or confirm gate |
| Empty canvas error | Draw ink first; check paths_json export |
| SymPy incomplete_step | Expected for partial expressions; user confirms |
| First request slow | Model weights loading (~1 GB TexTeller + UniMERNet) |

---

*End of full export — 2026-08-30*
