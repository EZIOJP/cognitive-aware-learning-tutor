# Math OCR — file index

**Exported:** 2026-08-19 · **Updated:** 2026-08-30  
Grouped by layer. Paths relative to repo root.

---

## Frontend — canvas (`src/components/math-canvas/`)

| File | Purpose |
|------|---------|
| `MathGridCanvas.tsx` | Primary grid canvas; ink-only PNG, pen/eraser, paths export |
| `TldrawMathCanvas.tsx` | tldraw canvas for Study Room |
| `useIdleMathOcr.ts` | Debounced idle OCR → `/api/math/ocr` |
| `OcrReviewPanel.tsx` | Per-line edit · confirm gate · provider badge (**2026-08-30**) |
| `useStrokeAnalytics.ts` | Live stroke + eraser events |
| `strokeMetrics.ts` | Bbox, angles, session aggregates |
| `lastBandBbox.ts` | Crop bbox for last-line idle OCR |
| `FixedGridOverlay.tsx` | CSS grid (not in PNG export) |
| `types.ts` | `MathCanvasHandle` interface |
| `index.ts` | Barrel exports |

## Frontend — pages & hooks

| File | Purpose |
|------|---------|
| `src/pages/math/MathPracticePage.tsx` | Practice + canvas + intervention |
| `src/pages/math/TrainPlaygroundPage.tsx` | Handwriting training loop |
| `src/pages/math/MathRecognizeTestPage.tsx` | Manual OCR test |
| `src/pages/math/OcrTrainingDataPage.tsx` | Dataset manager · import · retrain (**2026-08-30**) |
| `src/pages/study/StudyRoomPage.tsx` | Study Room + tldraw |
| `src/study-room/hooks/useStudyRoomOcr.ts` | tldraw PNG → OCR |
| `src/context/StudySessionContext.tsx` | Stuckness, auto-intervention, SRS |
| `src/app/components/AITutorIntervention.tsx` | Hint UI, confirm/fix LaTeX |
| `src/features/quiz/MathQuizAnswerPanel.tsx` | Quiz handwriting pad |
| `src/features/quiz/GlobalQuizRunner.tsx` | Quiz runner · OCR confirm gate (**2026-08-30**) |
| `src/api/mathClient.ts` | Typed `/api/math/*` client |
| `src/components/widgets/SymPyCalculatorWidget.tsx` | Hub SymPy widget |
| `src/plugins/math_tutor_plugin.tsx` | Math routes |
| `src/styles/education-canvas.css` | Canvas styles |

## Frontend — legacy

| File | Purpose |
|------|---------|
| `src/app/components/MathSplitWhiteboard.tsx` | Old split sketch canvas |
| `src/app/components/MathWhiteboard.tsx` | Old simple whiteboard |

---

## Backend — math module (`backend/math/`)

| File | Purpose |
|------|---------|
| `router.py` | FastAPI routes |
| `ocr_service.py` | Core OCR pipeline |
| `ocr_engine.py` | Dual-engine TexTeller + UniMERNet (**2026-08-30**) |
| `texteller_onnx.py` | TexTeller 3 ONNX |
| `unimernet_onnx.py` | UniMERNet-T ONNX wrapper (**2026-08-30**) |
| `pure_onnx_unimernet.py` | Vendored pure ONNX runtime (**2026-08-30**) |
| `sympy_repair.py` | SymPy re-OCR repair loop (**2026-08-30**) |
| `latex_repair.py` | LaTeX micro-fix rules (**2026-08-30**) |
| `latex_validate.py` | Bracket validators (**2026-08-30**) |
| `stroke_order.py` | Stroke sort normalization (**2026-08-30**) |
| `structure_learned.py` | MLP structure verifier (**2026-08-30**) |
| `structure_misseg_log.py` | Fraction mis-seg log (**2026-08-30**) |
| `mathwriting_import.py` | MathWriting bulk import (**2026-08-30**) |
| `mfd_onnx.py` | Formula box detection |
| `line_detect.py` | Multi-line bands |
| `structure_verify.py` | Structural confidence |
| `stroke_symbol.py` | Glyph disambiguation (+ real-ink retrain 2026-08-30) |
| `onnx_providers.py` | CUDA/CPU ONNX provider resolution (**2026-08-30**) |
| `retrain_service.py` | CSV → TexTeller fine-tune export (**2026-08-30**) |
| `structure_calibrate.py` | structure_verify threshold tuning (**2026-08-30**) |
| `intervention_handler.py` | Stuckness + hints |
| `intervention_log.py` | PNG + CSV logs |
| `training_log.py` | Handwriting dataset |
| `training_service.py` | Curriculum + progress |
| `answer_grade.py` | SymPy equivalence |
| `eval_service.py` | SymPy calculator |
| `ollama_tutor.py` | Optional Ollama hints/vision |
| `rule_tutor.py` | Rule-based hints |
| `srs_bridge.py` | → ReviewCard |
| `skills.py` | Skill tree |
| `generators/layer0.py` | Procedural SymPy questions |

## Backend — related

| File | Purpose |
|------|---------|
| `backend/quiz/handler.py` | Quiz grading uses `answer_grade` |
| `backend/vocab/routes.py` | Legacy `/api/vocab/math/practice/*` |
| `backend/integrations/nim_client.py` | NIM vision teacher (optional) |
| `backend/main.py` | Mounts math router |
| `backend/requirements-ocr.txt` | Optional OCR deps |

---

## Tests (`tests/`)

| File | Purpose |
|------|---------|
| `test_math_ocr.py` | OCR pipeline |
| `test_math_ocr_phases.py` | UniMERNet / repair / validators (**2026-08-30**) |
| `test_stroke_metrics.py` | Stroke metrics |
| `test_line_detect_structure.py` | Line detect + structure |
| `test_intervention_handler.py` | Intervention |
| `test_tutor_silence.py` | Low-confidence silence |
| `test_math_quiz_multi.py` | SymPy quiz grading |
| `test_math_full_track.py` | E2E math track |
| `test_math_skills.py` | Layer-0 generators |
| `test_training_log.py` | Training dataset |
| `test_math_tutor_gateway.py` | Tutor LLM gateway |

---

## Scripts

| File | Purpose |
|------|---------|
| `scripts/install_ocr.bat` / `.sh` | Install OCR deps |
| `scripts/download_texteller.bat` / `.sh` | Download TexTeller weights |
| `scripts/retrain_texteller.py` / `.bat` | TexTeller export/train (**2026-08-30**) |
| `scripts/retrain_stroke_symbol.py` / `.bat` | Stroke disambiguator retrain (**2026-08-30**) |
| `scripts/recalibrate_structure.py` / `.bat` | Structure verify calibration (**2026-08-30**) |
| `scripts/install_unimernet.bat` / `.py` | UniMERNet auto-install (**2026-08-30**) |
| `scripts/convert_unimernet_onnx.py` | .pth → ONNX export (**2026-08-30**) |
| `scripts/eval_ocr_cdm.py` | CDM-lite offline eval (**2026-08-30**) |
| `scripts/sync_math_ocr_export.py` | Refresh this export folder from live repo |
| `scripts/download_texteller.bat` / `.sh` | Download TexTeller weights |
| `scripts/experiments/phase0_exp1_latency.py` | Latency benchmarks |
| `scripts/experiments/phase0_exp3_segment.py` | Segmentation experiments |
| `scripts/experiments/phase0_make_samples.py` | Synthetic samples |
| `scripts/experiments/phase1_real_ink_check.py` | Real ink validation |
| `scripts/experiments/mathwriting_symbol_proto.py` | Symbol proto |

---

## Docs (canonical)

| File | Purpose |
|------|---------|
| `docs/MATH_TUTOR_VISION_PIPELINE.md` | North star + phases |
| `docs/CANVAS_OCR_ROADMAP.md` | OCR polish backlog |
| `docs/superpowers/specs/2026-08-08-math-multiline-ocr-tutor-design.md` | Approved design |
| `docs/superpowers/specs/2026-08-08-phase0-ocr-results.md` | Benchmark results |
| `docs/superpowers/specs/2026-07-17-mental-math-aptitude-design.md` | Mental math design |
| `docs/DEPENDENCIES.md` | OCR install tier B |
| `docs/decisions/ADR-001-quiz-practice-orchestration.md` | Quiz + math lanes |

---

## Data artifacts (runtime)

| Path | Purpose |
|------|---------|
| `data_logs/interventions/*.png` | Intervention snapshots |
| `data_logs/DSC_interventions_*.csv` | Intervention index |
| `data_logs/DSC_handwriting_dataset.csv` | Training labels |
| `data_logs/DSC_Kinematics.csv` | Stroke kinematics |
| `data/math/unimernet/artifacts/` | UniMERNet ONNX encoder/decoder (**2026-08-30**) |
| `data/math/unimernet/models/` | Tokenizer + unimernet_tiny.pth |
| `data/math/structure_thresholds.json` | Calibrated geometry thresholds |
| `data/math/structure_calibration_report.json` | Last calibration scores |
| `data/math/texteller_finetune/` | TexTeller export bundle |
| `data/math/stroke_symbol_model.npz` | Stroke disambiguator weights |

---

**Total indexed:** ~96 source copies in this folder (+ runtime logs).

**Refresh source copies after code changes:**

```bat
python scripts\sync_math_ocr_export.py
```

---

## Bundled source copies (this export folder)

| Folder | Contents |
|--------|----------|
| `frontend/src/components/math-canvas/` | All 9 canvas/OCR hook files |
| `frontend/src/pages/math/` | Practice, train, recognize-test pages |
| `frontend/src/...` | StudySessionContext, AITutorIntervention, mathClient, plugin, legacy whiteboards |
| `backend/math/` | Full module (router, ocr_service, texteller, intervention, training, generators, …) |
| `backend/models/` | `math.py`, `math_question.py` |
| `backend/quiz/handler.py` | Quiz grading → SymPy |
| `backend/vocab/routes.py` | Legacy math practice routes |
| `backend/integrations/nim_client.py` | Optional NIM vision |
| `backend/main.py` | App mount point |
| `backend/requirements-ocr.txt` | OCR pip deps |

Tests and scripts remain in the repo only (see paths above).
