# Math OCR close-out — 2026-08-30

**Updated:** 2026-08-30  
**Scope:** Priority fixes from architecture review (GPU, retrain loop, stroke disambiguator, structure calibration).

---

## Summary

| # | Item | Status | Where |
|---|------|--------|--------|
| 1 | CUDA ONNX providers (RTX / GPU) | **Shipped** | `backend/math/onnx_providers.py`, `texteller_onnx.py`, `mfd_onnx.py` |
| 2 | TexTeller fine-tune export from CSV | **Shipped** | `backend/math/retrain_service.py`, `scripts/retrain_texteller.py` |
| 3 | `stroke_symbol` real-ink retrain | **Shipped** | `stroke_symbol.py`, `scripts/retrain_stroke_symbol.py` |
| 4 | `structure_verify` calibration | **Shipped** | `structure_calibrate.py`, `scripts/recalibrate_structure.py` |

---

## 1. GPU ONNX (2026-08-30)

- Auto: `CUDAExecutionProvider` → `CPUExecutionProvider` fallback
- Env: `OCR_ONNX_DEVICE=auto|cuda|cpu`
- Install: `pip uninstall onnxruntime && pip install onnxruntime-gpu`
- Status field: `GET /api/math/ocr/status` → `execution_provider`

---

## 2. TexTeller retrain (2026-08-30)

**Was:** `POST /api/math/train/retrain` stub (“export only”).

**Now:**

```http
POST /api/math/train/retrain?mode=export
POST /api/math/train/retrain?mode=train
```

```bat
scripts\retrain_texteller.bat
```

**Output:** `data/math/texteller_finetune/train/images/` + `formulas.jsonl`  
**Optional train:** clone TexTeller, set `TEXTELLER_TRAIN_REPO`, `pip install texteller[train]`, `--mode train`

---

## 3. Stroke-symbol real ink (2026-08-30)

```http
POST /api/math/train/retrain-stroke-symbol?min_samples=3
```

```bat
scripts\retrain_stroke_symbol.bat
```

Reads `paths_json_path` + confirmed labels from `DSC_handwriting_dataset.csv`.  
Blends synthetic augments. Writes `data/math/stroke_symbol_model.npz`.

---

## 4. Structure verify calibration (2026-08-30)

```http
POST /api/math/train/recalibrate-structure?min_samples=5
```

```bat
scripts\recalibrate_structure.bat
```

**Output:** `data/math/structure_thresholds.json`, `structure_calibration_report.json`  
Updates tutor/SRS silence via `STRUCTURAL_SILENCE_THRESHOLD`.

---

## Suggested operator order

See **[MATH_OCR_BUILD_AND_CHANGES.md](./MATH_OCR_BUILD_AND_CHANGES.md)** §7 for full steps.

1. Confirm samples in Train Playground (`/math-tutor/train`)
2. `scripts\install_ocr.bat` + `onnxruntime-gpu` if using RTX
3. `scripts\retrain_stroke_symbol.bat`
4. `scripts\recalibrate_structure.bat`
5. When ≥50 samples: `scripts\retrain_texteller.bat`
6. Restart API · check `GET /api/math/ocr/status`

---

## Still deferred

- Production OCR accuracy polish (`docs/CANVAS_OCR_ROADMAP.md`)
- Automatic ONNX weight swap after TexTeller fine-tune
- WebGazer / real EEG in stuckness
- Stroke-sequence symbol classifier trained on MathWriting (research prototype in
  `scripts/experiments/mathwriting_symbol_proto.py`) — separate from the shipped
  bulk importer `backend/math/mathwriting_import.py`, which landed in Phase B
  and is wired to `POST /api/math/train/import` but has not yet been run on a
  live excerpt

---

## Export folder dates

| Doc | Initial export | Last updated |
|-----|----------------|--------------|
| `MATH_OCR_ARCHITECTURE_EXPORT.md` | 2026-08-19 | **2026-08-30** |
| `FILE_INDEX.md` | 2026-08-19 | **2026-08-30** |
| This file | — | **2026-08-30** |
