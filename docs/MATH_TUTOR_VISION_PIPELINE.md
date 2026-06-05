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
| Manual **Ask tutor** | Shipped (rule-based) | `POST /api/math/tutor/hint`, `backend/math/rule_tutor.py` |
| Optional Ollama hints | Opt-in (`OLLAMA_ENABLED=0`) | `backend/math/ollama_tutor.py` |
| EEG simulation + hub metric | Shipped | `StudySessionContext`, `backend/eeg/` |
| Python focus mirror (not browser) | Shipped | `backend/face_tracker.py` |
| Auto intervention UI | Partial | `AITutorIntervention.tsx` exists; auto-trigger off in `config.ts` |
| `/api/intervention` + DSC CSV flywheel | Not wired | Described in `backend_example.py` only |
| WebGazer gaze | Not implemented | Research only |
| Pix2Text / OpenCV / SymPy pipeline | Not implemented | Research only |
| Pydantic structured Ollama output | Not implemented | Research only |

## Recommended stack (8 GB VRAM)

**Do not** run full-screen LLaVA on every pointer move. Use a **two-stage** path:

1. **Trigger** — stuckness heuristic (pause + eraser + EEG sim + optional face attention), debounced snapshot.
2. **Preprocess** — OpenCV: grayscale → dilate/erode → connected components → crop regions; mask scribble-dense areas using stroke overlap from `exportPaths()` when available.
3. **Recognize** — prefer **Pix2Text** or **pix2tex** for LaTeX on crops; fall back to raw image for SymPy parse failures (“incomplete step”).
4. **Tutor** — text LLM via Ollama (`llama3.2` ~2–4 GB) with **structured JSON** schema; use vision model (`llava`, `OLLAMA_VISION_MODEL`) only when OCR fails or step is incomplete.
5. **VRAM** — `keep_alive=10m` during study; `keep_alive=0` after session; never stack multiple 7B models.

| Approach | VRAM | Latency | Freehand math |
|----------|------|---------|----------------|
| LLaVA 7B only | ~4.5–5.5 GB | High | Hallucinates on messy strokes |
| pix2tex + LLM | ~200 MB + LLM | Low | Good single equations |
| Pix2Text + LLM | ~800 MB + LLM | Medium | Better messy layouts |
| **Recommended** | Pix2Text/pix2tex → text LLM; LLaVA fallback | | |

## Canvas telemetry (frontend)

- **Library:** keep `react-sketch-canvas` — already has `exportImage`, `exportPaths`; matches research.
- **Snapshots:** debounce on pause + eraser burst, not every frame; crop to stroke bounding box (track min/max x/y over 60s window).
- **Kinematics:** `PointerEvent.getCoalescedEvents()` in a hook; log velocity + inter-stroke gaps; optional `DSC_Kinematics.csv` append.
- **Paths API:** expose `exportPaths()` from `MathSplitWhiteboard` for backend scribble masking.

## Backend endpoints (target)

| Endpoint | Role |
|----------|------|
| `POST /api/math/tutor/hint` | Today: manual + rules; keep as fallback |
| `POST /api/math/intervention` | New: stuckness-triggered pipeline |
| `POST /api/math/ocr` | Optional: image → LaTeX + `incomplete_step` flag |

**Pydantic response (Ollama `format=` schema):**

```python
class SocraticIntervention(BaseModel):
    mathematical_step_identified: str
    point_of_confusion: str
    socratic_hint_text: str
    confidence_score: float  # 0.0–1.0
```

Store snapshots under `data_logs/interventions/{session_id}/`; index in `DSC_Interventions.csv`.

## Stuckness score (heuristic v1)

Combine (no GPU required for v1):

- Canvas idle > N seconds after last stroke
- Eraser events in last window
- EEG gamma vs personal baseline (sim or real)
- Optional: `face_attention` from Python mirror POST
- Optional: WebGazer fixation on canvas bbox (later)

Weights tunable; trigger only above threshold to save VRAM.

## Phased implementation (maps to ROADMAP Phase 3)

### 3a — Software only (doable now, no GPU)

- [ ] Stuckness heuristic + debounced `exportPng` crop
- [ ] Mount `AITutorIntervention` on math practice when score fires
- [ ] `POST /api/math/intervention` stub → rule tutor + log to CSV
- [ ] `exportPaths()` + idle/eraser counters in `StudySessionContext`

### 3b — After laptop / Ollama

- [ ] Ollama structured JSON (`format=SocraticIntervention.schema`)
- [ ] `OLLAMA_ENABLED=1`, `keep_alive` tuning
- [ ] Optional `OLLAMA_VISION_MODEL` for incomplete steps only

### 3c — OCR pipeline (CPU OK)

- [ ] OpenCV segmentation service
- [ ] Pix2Text or pix2tex dependency (optional extra in `requirements.txt`)
- [ ] SymPy validate LaTeX → `incomplete_step` branch

### 3d — Multimodal (Phase 2 hardware + optional WebGazer)

- [ ] Real EEG in stuckness weights
- [ ] WebGazer.js gaze on canvas region
- [ ] Face calibration JSON consumed by `face_tracker.py`

## Dependencies to add (when implementing 3b–3c)

```text
opencv-python-headless
pix2text   # or pix2tex
sympy
```

Keep OCR **optional** so `run.bat` works on machines without GPU.

## References (external)

- Canvas: [react-sketch-canvas](https://www.npmjs.com/package/react-sketch-canvas), Konva/Fabric comparison (Velt 2026)
- OCR: PyImageSearch handwriting pipeline (contours + CNN); Pix2Text / pix2tex for LaTeX
- Ollama: structured outputs, LLaVA vision models
- Pedagogy: Socratic JSON + chain-of-thought fields before `socratic_hint_text`
