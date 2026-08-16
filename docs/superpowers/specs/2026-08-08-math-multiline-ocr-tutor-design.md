# Design: Multi-line math OCR + live hints + SRS flywheel

**Date:** 2026-08-08  
**Status:** Approved direction (from Deep Research + CALT inventory) — implement in phases  
**Sources:** User report *Local Math OCR Tutor Architecture.md* (works cited §1–46); [MATH_TUTOR_VISION_PIPELINE.md](../../MATH_TUTOR_VISION_PIPELINE.md); existing `backend/math/*`, `backend/quiz/srs.py`

---

## 1. Verdict (take these; leave those)

### Keep (good parts)

| Idea | Why it fits CALT |
|------|------------------|
| **Freehand canvas** (reject 3-band as primary UX) | Matches current `MathGridCanvas` / practice whiteboard; 3-band adds cognitive load and fails on √ / integrals spanning bands |
| **Segment → per-crop OCR** | Pix2Text **MFD ONNX** (~80 MB) for formula boxes, then **TexTeller 3 ONNX** per crop (already shipped: `texteller_onnx.py`, model `Ji-Ha/TexTeller3-ONNX-dynamic`) |
| **Progressive / pause-triggered OCR** | Reuse stuckness + idle debounce ([MATH_TUTOR_VISION_PIPELINE](../../MATH_TUTOR_VISION_PIPELINE.md)); optional WebSocket later |
| **Incomplete → nudge, not fail** | Already have `incomplete_step` + SymPy gates in `ocr_service.py`; keep `evaluate=False` / timeout around `parse_latex` |
| **Hints on hot path; heavy work async** | Intervention + Ollama already exist; don’t block UI on full solutions |
| **Struggle → spaced review** | Wire math fails into existing **quiz SRS** (`backend/quiz/srs.py` is FSRS-inspired) + `skills.json` tags — prefer extend, don’t invent parallel BKT |
| **OCR noise must not poison SRS** | Confirm LaTeX when low confidence; skip FSRS update on recognition failure (report §4.3) |
| **ONNX CPU tuning** | Sequential + capped `intra_op` + no spinning — apply in `texteller_onnx.py` session options |
| **Day-1 experiments** | Thread profile, SymPy fuzz, MFD on whiteboard PNGs, SRS sandbox, progressive mock |

### Drop / defer

| Idea | Reason |
|------|--------|
| **3-band as primary writing UI** | Research **no-go**; optional later only for *digit training* drills |
| **Train custom CoMER / PosFormer** | Months of GPU work; use ONNX pretrained only |
| **Full py-fsrs greenfield DB** | CALT already has quiz SRS; map grades → that scheduler first; optional `py-fsrs` later if needed |
| **Mathpix as default** | Privacy; keep **opt-in** cloud fallback only after local fails |
| **Replace TexTeller with TrOCR** | TrOCR weak on 2D math; report agrees |
| **WebSocket-only OCR in week 1** | Can start with **HTTP crop-per-line** on pause; add WS when latency UX needs it |

### Reality checks vs our stack

- Docs already say **Pix2Text not implemented**; TexTeller replaced pix2tex on **Python 3.14**. Adding MFD may mean **MFD ONNX only** (CnSTD/YOLO) without full `pix2text` pip if 3.14 breaks — verify in Phase 0 experiment.
- Intervention + handwriting CSV flywheel already ship — extend them; don’t rewrite.
- Layer-0 generators + `skills.json` already tag skills — reuse for SRS skill_tag.

---

## 2. Target architecture (CALT-mapped)

```text
[React canvas] strokes + PNG (+ paths_json, stroke_metrics)
        │
        │  pause / stuckness / “Recognize” / per new line
        ▼
[FastAPI] preprocess (OpenCV — existing ocr_service)
        │
        ├─► [stroke-bbox Y-cluster]  (canvas primary)
        │         or projection-profile (image-only)
        │         MFD ONNX only if both fail on real ink
        ▼
[TexTeller ONNX] per crop → LaTeX[]   (EXISTING)
        │
        ▼
[structure_verify] geometry vs LaTeX → structural_confidence
        │                 low → tutor silence
        ▼
[Normalize + SymPy] → incomplete_step? → structural nudge
        │                 else grade vs expected
        ▼
[Hot path] rule_tutor / ollama_tutor hint   (EXISTING intervention)
[Background] map intervention severity → SRS grade 1–4
        │
        ▼
[quiz/srs.py + skill_tag] due review / generative twin problem
```

**Latency budget (aspirational p50, consumer CPU):**

| Stage | Target |
|-------|--------|
| Stroke cluster / crop | &lt; 50 ms |
| MFD detect | 100–300 ms |
| TexTeller per line | 500–1200 ms (tuned) |
| SymPy | &lt; 100 ms |
| First tutor token | 400–800 ms (Ollama) or &lt;50 ms (rules) |
| **First useful feedback** | aim **&lt; 2 s** after pause |

---

## 3. SRS grade mapping (reuse quiz SRS)

Map intervention outcomes → rating (align with report §4.2):

| Grade | Meaning | Trigger examples |
|-------|---------|------------------|
| 1 Again | Full solution shown / abandoned | `correct` never; tutor gave final answer |
| 2 Hard | Heavy scaffolding | Multiple interventions same problem |
| 3 Good | Minor hint then success | One Socratic nudge |
| 4 Easy | No intervention | Clean solve |

**Noise rules:** if OCR `confidence` low or hallucination filter trips → ask “I read … OK?” before Grade 1–2; else log recognition_failure and **skip** SRS.

---

## 4. Phased plan (CALT-sized)

### Phase 0 — Validate (≤2 days)

1. ONNX thread isolation profile on TexTeller (report experiment 1).  
2. Run MFD ONNX on 10 multi-line whiteboard exports vs Y-gap heuristic (experiment 3).  
3. Confirm `pix2text` / MFD install on this machine’s Python — document fallback = stroke clustering only.  
4. **Whole-canvas vision model test:** same multi-line samples through Ollama vision (e.g. Qwen2.5-VL) vs MFD+TexTeller pipeline — if the single VLM call wins on accuracy at acceptable latency, it may replace the detection pipeline entirely.

**Go:** TexTeller p50 &lt; ~1.5 s/line with tuning; MFD or heuristic splits 3-line samples usefully.

> **✅ Phase 0 result (2026-08-08): GO.** TexTeller p50 **0.75 s/line** (thread tuning gained only ~2% — skip it). Projection-profile segmentation split **5/5** multi-line samples in &lt;15 ms with near-perfect per-line OCR. MFD ONNX (80 MB) loads with plain onnxruntime and infers in ~0.23 s — use it directly, **do not** install the pix2text package (~30 extra deps). Whole-image TexTeller emits `\begin{array}` for stacked equations but silently dropped a line once → fallback only. Ollama not installed → VLM path deferred. Caveat: samples were synthetic printed math; real handwriting will stress segmentation more. Full data: [2026-08-08-phase0-ocr-results.md](2026-08-08-phase0-ocr-results.md).

### Phase 1 — Multi-line OCR (1–2 weeks) — **DONE 2026-08-08**

- Add `detect_formula_boxes(image) -> boxes[]` — **primary for canvas: stroke-bbox Y-clustering** ([`backend/math/line_detect.py`](../../../backend/math/line_detect.py)); **image-only: projection-profile heuristic** (Phase 0 validated). Fraction guard merges numerator/bar/denominator. **MFD ONNX** ([`mfd_onnx.py`](../../../backend/math/mfd_onnx.py)) used when both heuristics yield &lt;2 bands.  
- `recognize_multiline` in [`ocr_service.py`](../../../backend/math/ocr_service.py): crop → TexTeller each → join with `\\\\` or list of steps.  
- Extend `POST /api/math/ocr` response: `{ lines: [{latex, bbox, confidence, structural_confidence}], latex, structural_confidence }`.  
- Keep whole-image TexTeller as fallback when detection yields &lt;2 bands.  
- **Relation layer v0** ([`structure_verify.py`](../../../backend/math/structure_verify.py)): pure geometry on stroke bboxes (superscript / subscript / fraction / sqrt) cross-checked against LaTeX → `structural_confidence`. Low confidence feeds the **tutor silence rule** in [`intervention_handler.py`](../../../backend/math/intervention_handler.py).
- **Stroke-symbol disambiguator** ([`stroke_symbol.py`](../../../backend/math/stroke_symbol.py)): low-confidence short glyphs may be rescued from paths_json.

### Phase 2 — Progressive tutor path — **DONE 2026-08-08**

- Idle pause → OCR **active crop** via `crop_bbox` on `POST /api/math/ocr` + [`useIdleMathOcr`](../../../src/components/math-canvas/useIdleMathOcr.ts) (~1.4s debounce, last-line band).  
- Incomplete → existing nudge path.  
- **Tutor silence** wired in FE: [`AITutorIntervention`](../../../src/app/components/AITutorIntervention.tsx) skips empty silent panels; checkpoint **Yes / Fix reading** → recover(true) / `PATCH .../correct`.  
- Dismiss → `learner_recovered=false` (no SRS success).  
- WebSocket stroke stream deferred (HTTP idle crop sufficient).

### Phase 3 — SRS flywheel — **DONE 2026-08-08**

- Struggle enqueue + recover/correct success via [`srs_bridge.py`](../../../backend/math/srs_bridge.py).  
- Human confirm gate in UI + backend skip when silent / low conf.

### Track B — MathWriting stroke classifier (parallel, non-blocking)

- Google [MathWriting](https://arxiv.org/abs/2404.10690) (CC BY-NC-SA 4.0) isolated-symbol subset (~6k symbols).  
- Prototype a small stroke-sequence classifier (GRU over resampled x,y,pen-state deltas) in a throwaway env; export ONNX for later inference.  
- Slot in later as a **disambiguator** for low-confidence symbols — not a v1 recognizer replacement.  
- Scripts: `scripts/experiments/mathwriting_*`.  
- **Deferred:** full stroke seq2seq HMER / MyScript parity (multi-year R&amp;D).

> **Track B prototype (2026-08-08):** Downloaded official MathWriting **excerpt** (1.5 MB). Parsed InkML strokes; excerpt has few short isolated labels, so augmented with synthetic digit/operator strokes. Numpy stroke-feature softmax reached **~94%** held-out (excerpt run) / **~98%** on shipped synthetic model at `data/math/stroke_symbol_model.npz`. **Wired** into OCR as low-confidence short-glyph disambiguator via [`stroke_symbol.py`](../../../backend/math/stroke_symbol.py). Full MyScript-level seq2seq remains deferred.

### Explicitly not in v1

3-band primary UI · custom full-expression model training · BKT · Mathpix-required path · full tutor rewrite · MyScript parity.

---

## 5. Key files to touch

| Area | Files |
|------|--------|
| OCR | `backend/math/ocr_service.py`, `texteller_onnx.py`, `line_detect.py`, `structure_verify.py`, `mfd_onnx.py`, `stroke_symbol.py` |
| API | `backend/math/router.py` |
| Tutor | `intervention_handler.py`, `rule_tutor.py`, `ollama_tutor.py` |
| SRS | `backend/math/srs_bridge.py` → `backend/quiz/review_cards.py` |
| Skills | `backend/math/skills.json`, `generators/layer0.py` |
| UI | `MathGridCanvas.tsx`, `MathPracticePage.tsx`, `MathRecognizeTestPage.tsx` |
| Deps | `backend/requirements-ocr.txt`, `scripts/install_ocr.bat` |
| Track B | `scripts/experiments/mathwriting_*`, `data/math/stroke_symbol_model.npz` |
| Docs | this spec; update `MATH_TUTOR_VISION_PIPELINE.md` when Phase 1 lands |

---

## 6. References (from report + repo)

- TexTeller: https://github.com/OleehyO/TexTeller · ONNX community / Ji-Ha dynamic ONNX (in-repo)  
- Pix2Text MFD 1.5 ONNX: https://huggingface.co/breezedeus/pix2text-mfd-1.5  
- MathWriting dataset: https://arxiv.org/abs/2404.10690  
- ONNX threading: https://onnxruntime.ai/docs/performance/tune-performance/threading.html  
- FSRS overview: https://github.com/open-spaced-repetition/awesome-fsrs  
- CALT: `docs/MATH_TUTOR_VISION_PIPELINE.md`, `backend/quiz/srs.py`, `backend/math/ocr_service.py`

---

## 7. Next action

Phase 0 **GO** (see results doc). Phase 1 multi-line OCR + stroke-aware track is the active build: line_detect, recognize_multiline, structure_verify, tutor silence. Track B MathWriting prototype runs in parallel and must not block v1.
