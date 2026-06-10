# Math tutor vision pipeline (research → implementation)

Condensed from your local multimodal math tutor research (RTX 5060 / 8 GB VRAM target). Use this with [CURRENT_ARCHITECTURE.md](./CURRENT_ARCHITECTURE.md), [FUTURE_VISION.md](./FUTURE_VISION.md), and [ROADMAP.md](./ROADMAP.md).

## Target loop (north star)

```text
draw on whiteboard → stuckness score → cropped snapshot
  → OpenCV segment → OCR/LaTeX (or VLM if incomplete)
  → Ollama Socratic JSON → hint UI → DSC_* logs
```

## What exists today

| Piece | Status | Location |
|-------|--------|----------|
| `react-sketch-canvas` whiteboard | Shipped | `src/app/components/MathSplitWhiteboard.tsx` |
| Manual **Ask tutor** | Shipped (rule-based + optional Ollama) | `POST /api/math/tutor/hint`, `backend/math/rule_tutor.py` |
| Optional Ollama hints | Opt-in (`OLLAMA_ENABLED=0`) | `backend/math/ollama_tutor.py` |
| EEG simulation + hub metric | Shipped | `StudySessionContext`, `backend/eeg/` |
| Python focus mirror (not browser) | Shipped | `backend/face_tracker.py` |
| Auto intervention UI | Shipped | `AITutorIntervention.tsx` on `MathPracticePage`; `config.intervention.autoTrigger` |
| `POST /api/math/intervention` + DSC CSV | Shipped | `backend/math/intervention_handler.py`, `intervention_log.py` |
| `POST /api/math/ocr` | Shipped | TexTeller ONNX (Python 3.14); multi-tier fallback |
| Eraser + idle stuckness loop | Shipped | `StudySessionContext`, `MathSplitWhiteboard` handle |
| NIM teacher (opt-in) | Shipped | `NIM_API_KEY` → Tier 0 in `ocr_service.py` |
| WebGazer gaze | Not implemented | Research only |
| Pix2Text | Not implemented | TexTeller ONNX used instead of pix2tex on 3.14 |

## Recommended stack (8 GB VRAM)

**Do not** run full-screen LLaVA on every pointer move. Use a **two-stage** path:

1. **Trigger** — stuckness heuristic (pause + eraser + EEG sim + optional face attention), debounced snapshot.
2. **Preprocess** — OpenCV: grayscale → dilate/erode → connected components → crop regions; mask scribble-dense areas using stroke overlap from `exportPaths()` when available.
3. **Recognize** — TexTeller ONNX on crops; Ollama vision fallback; optional NIM Nemotron teacher label.
4. **Tutor** — text LLM via Ollama (`qwen2.5-math:7b`) with LaTeX-aware prompts; vision model only when OCR incomplete.
5. **VRAM** — `keep_alive=-1` during study session for math model; never stack multiple 7B models.

## Canvas telemetry (frontend)

- **Library:** `react-sketch-canvas` — `exportImage`, `exportPaths`, eraser counter on handle.
- **Snapshots:** debounced on idle + stuckness score; paths JSON sent with intervention.
- **Kinematics:** optional `DSC_Kinematics.csv` — not wired yet.
- **Paths API:** `exportPaths()` + `getEraserEventCount()` on `MathSplitWhiteboardHandle`.

## Backend endpoints

| Endpoint | Role |
|----------|------|
| `POST /api/math/tutor/hint` | Manual + rules; fallback |
| `POST /api/math/intervention` | Stuckness-triggered OCR → hint → DSC log |
| `POST /api/math/ocr` | Image → LaTeX + `incomplete_step` + tiers |
| `PATCH /api/math/intervention/{id}/recover` | Learner recovered / dismissed |
| `PATCH /api/math/intervention/{id}/correct` | Human correct LaTeX → `DSC_handwriting_dataset.csv` |

Store snapshots under `data_logs/interventions/{session_snapshot_id}.png`; index in `DSC_interventions_{date}.csv`.

## Stuckness score (heuristic v1 — shipped)

```text
stuckness = 0.4·min(idle/90,1) + 0.3·min(erasers/5,1) + 0.3·min((gamma-55)/30,1)
fire when stuckness > 0.5 and idle ≥ 45s and cooldown ≥ 120s
```

## Phased implementation (maps to ROADMAP Phase 3)

### 3a — Software only

- [x] Stuckness heuristic + debounced `exportPng` crop
- [x] Mount `AITutorIntervention` on math practice when score fires
- [x] `POST /api/math/intervention` → OCR + rule/Ollama tutor + CSV log
- [x] `exportPaths()` + idle/eraser counters in `StudySessionContext`

### 3b — After laptop / Ollama

- [x] Ollama structured JSON (`SocraticHint` schema)
- [ ] `OLLAMA_ENABLED=1` in production `.env` (opt-in per machine)
- [x] `OLLAMA_VISION_MODEL` for incomplete steps (Tier 2 fallback)

### 3c — OCR pipeline (CPU OK)

- [x] OpenCV segmentation + paths masking in `ocr_service.py`
- [x] TexTeller ONNX (replaces pix2tex on Python 3.14)
- [x] SymPy validate LaTeX → `incomplete_step` + confidence gate

### 3d — Multimodal (Phase 2 hardware + optional WebGazer)

- [ ] Real EEG in stuckness weights (sim works today)
- [ ] WebGazer.js gaze on canvas region
- [ ] Face calibration JSON consumed by `face_tracker.py`

## Dependencies (OCR tier)

```text
opencv-python-headless
onnxruntime + optimum + transformers  # TexTeller ONNX
sympy
```

Install: `scripts\install_ocr.bat` (Windows) or `./scripts/install_ocr.sh`.

Optional: `NIM_API_KEY` for Nemotron vision teacher labels.
