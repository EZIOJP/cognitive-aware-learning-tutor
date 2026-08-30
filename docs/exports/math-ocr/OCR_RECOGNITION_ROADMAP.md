# Math OCR recognition — feature roadmap

**Updated:** 2026-08-30  
**Goal:** Proper multi-line handwritten math recognition (production quality).

Current stack: TexTeller ONNX + line detect + structure verify + stroke_symbol ensemble + learned structure MLP.

---

## Phase A — Done (2026-08-30)

- [x] GPU ONNX providers
- [x] Training data export + editable dataset UI
- [x] Stroke-symbol real-ink retrain
- [x] Structure verify calibration
- [x] Recognize-test: lines, confidence, structural_confidence

---

## Phase B — Dataset quality — Done (2026-08-30)

- [x] Bulk import MathWriting excerpt (`POST /api/math/train/import`)
- [x] Filter: `has_paths_json` on list/export
- [x] Duplicate detection (`GET /api/math/train/duplicates`)
- [x] Train Playground → link to saved sample in training-data

---

## Phase C — Recognition UX — Done (2026-08-30)

- [x] **Practice + quiz:** shared `OcrReviewPanel` — per-line OCR + edit
- [x] **Low confidence gate:** block quiz submit until Confirm
- [x] **Crop band preview** on OCR review panel
- [x] **Execution provider** badge on practice / quiz / review
- [x] Save corrected OCR from practice → training dataset (one tap)

---

## Phase D — Model quality — Done (2026-08-30)

- [x] TexTeller fine-tune export (50+ samples) — train mode via env
- [x] Hot-swap: `TEXTELLER_FINETUNED_MODEL` + `POST /train/reload-model`
- [x] Ensemble: TexTeller + stroke_symbol vote + NIM auto-confirm
- [x] NIM teacher auto-confirm when agree + high confidence

---

## Phase E — Advanced structure — Done (2026-08-30)

- [x] Learned MLP verifier (`structure_learned.py`) blends with geometry
- [x] Matrix / aligned environment detection
- [x] Coalesced pointer kinematics (`coalescePointerStrokes` in strokeMetrics)
- [x] Fraction guard tuning via mis-segmentation log (`structure_misseg_log.py`)

---

## Phase F — Out of scope unless reopened

- WebGazer gaze in stuckness
- Real EEG hardware
- Full Pix2Text MFR package
- Cloud OCR default (Mathpix)

---

## Success metrics

| Metric | Target |
|--------|--------|
| Single-digit accuracy (local ink) | >95% after stroke retrain |
| Curriculum prompt match rate | >80% confirm without correct |
| Multi-line fraction | structure agree >70% |
| OCR p50 latency (GPU) | <1.0s per line |
| Tutor false interrupt rate | ↓ via structure calibration |

---

## Pages map

| URL | Purpose |
|-----|---------|
| `/math-tutor/recognize-test` | Debug OCR |
| `/math-tutor/train` | Collect samples |
| `/math-tutor/training-data` | Edit / delete / import / retrain |
| `/math-tutor/practice/:id` | Production use + tutor + save OCR |

See [MATH_OCR_BUILD_AND_CHANGES.md](./MATH_OCR_BUILD_AND_CHANGES.md) for build steps.
