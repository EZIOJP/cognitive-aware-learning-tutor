# Math OCR — changes, build & run guide

**Updated:** 2026-08-30  
**Repo:** Cognitive-Aware Learning Tutor  
**Audience:** Owner / developer — what changed, how to install, build, run, and improve OCR.

Related: [OCR_CLOSEOUT_2026-08-30.md](./OCR_CLOSEOUT_2026-08-30.md) · [MATH_OCR_ARCHITECTURE_EXPORT.md](./MATH_OCR_ARCHITECTURE_EXPORT.md)

---

## 1. Changes done (2026-08-30)

### 1.1 GPU ONNX acceleration

| Before | After |
|--------|--------|
| TexTeller + MFD hardcoded `CPUExecutionProvider` | Auto `CUDAExecutionProvider` → CPU fallback |
| RTX GPU idle during OCR | Uses GPU when `onnxruntime-gpu` installed |

**Files:** `backend/math/onnx_providers.py`, `texteller_onnx.py`, `mfd_onnx.py`, `router.py` (`execution_provider` on status)

**Env vars:**

| Variable | Values | Default |
|----------|--------|---------|
| `OCR_ONNX_DEVICE` | `auto`, `cuda`, `cpu` | `auto` |
| `TEXTELLER_CACHE_DIR` | path to HF cache | optional |
| `TEXTELLER_MODEL_ID` | HuggingFace model id | `Ji-Ha/TexTeller3-ONNX-dynamic` |

---

### 1.2 TexTeller retrain pipeline (was stub)

| Before | After |
|--------|--------|
| `POST /train/retrain` returned `"status": "stub"` | Exports `DSC_handwriting_dataset.csv` → TexTeller train layout |
| CSV collected data nothing read | `formulas.jsonl` + PNG copies under `data/math/texteller_finetune/` |

**Files:** `backend/math/retrain_service.py`, `scripts/retrain_texteller.py`, `scripts/retrain_texteller.bat`

**Optional:** `--mode train` launches TexTeller `accelerate launch train.py` if `TEXTELLER_TRAIN_REPO` is set.

---

### 1.3 Stroke-symbol disambiguator — real ink

| Before | After |
|--------|--------|
| Trained only on synthetic ellipses/lines | Retrains from confirmed `paths_json` in handwriting CSV |
| 8 fixed classes, fake strokes | Dynamic labels (digits, operators, variables) + synthetic augments |

**Files:** `backend/math/stroke_symbol.py`, `scripts/retrain_stroke_symbol.py`, `scripts/retrain_stroke_symbol.bat`

**Output:** `data/math/stroke_symbol_model.npz`

---

### 1.4 Structure verify calibration

| Before | After |
|--------|--------|
| Fixed ratios (e.g. superscript `< 0.7× median_h`) | Tunable thresholds in JSON |
| Hand-tuned silence at 0.45 | `silence_threshold` recalibrated from samples |

**Files:** `backend/math/structure_verify.py`, `backend/math/structure_calibrate.py`, `scripts/recalibrate_structure.py`

**Outputs:** `data/math/structure_thresholds.json`, `data/math/structure_calibration_report.json`

---

### 1.5 New API routes (admin unless noted)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/math/ocr/status` | OCR ready + `execution_provider` |
| POST | `/api/math/train/retrain` | TexTeller export / optional train |
| POST | `/api/math/train/retrain-stroke-symbol` | Stroke disambiguator retrain |
| POST | `/api/math/train/recalibrate-structure` | Geometry threshold calibration |

Existing routes unchanged: `/api/math/ocr`, `/intervention`, `/train/sample`, etc.

---

### 1.5 Phases B–E — full OCR recognition stack (2026-08-30)

| Area | Delivered |
|------|-----------|
| **B Dataset** | MathWriting import, duplicate detect/cleanup, paths_json filter, Playground→sample link |
| **C UX** | `OcrReviewPanel`, quiz submit gate, crop preview, provider badge, practice save-to-training |
| **D Models** | Ensemble vote, NIM auto-confirm, `TEXTELLER_FINETUNED_MODEL` + reload API |
| **E Structure** | Learned MLP, matrix detect, coalesced strokes, mis-segmentation log |

**New API routes:**

| Method | Path |
|--------|------|
| POST | `/api/math/train/import` |
| GET | `/api/math/train/duplicates` |
| POST | `/api/math/train/duplicates/cleanup` |
| POST | `/api/math/train/reload-model` (admin) |
| GET | `/api/math/train/samples?has_paths_json=true` |

**Pages:** `/math-tutor/training-data` · `/math-tutor/train` · quiz math handwrite · `/math-tutor/practice/:id`

See [OCR_RECOGNITION_ROADMAP.md](./OCR_RECOGNITION_ROADMAP.md) — phases A–E complete.

---

## 2. Prerequisites

| Requirement | Notes |
|-------------|--------|
| **Python** | 3.10–3.12 ideal; 3.14 works for TexTeller ONNX (not pix2tex) |
| **Node.js** | 20 LTS+ |
| **Git** | Clone repo |
| **NVIDIA GPU** | Optional; RTX 5060 etc. for faster OCR |
| **CUDA** | Must match `onnxruntime-gpu` wheel if using GPU |

Full project deps: [docs/DEPENDENCIES.md](../../DEPENDENCIES.md) · [docs/SETUP_AND_COMMANDS.md](../../SETUP_AND_COMMANDS.md)

---

## 3. First-time build (whole app)

From repo root:

```bat
run.bat
```

This creates `.venv`, installs Python + npm deps, runs Alembic migrations, starts:

- **Frontend:** http://localhost:5173  
- **API:** http://localhost:8000  
- **Health:** http://localhost:8000/health  

After `git pull` or dependency changes:

```bat
scripts\setup.bat
```

Manual equivalent:

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -U pip
pip install -r backend\requirements.txt
python -m alembic upgrade head
npm install
npm run build
```

---

## 4. Math OCR stack install

### 4.1 CPU (default)

```bat
scripts\install_ocr.bat
scripts\download_texteller.bat
```

Installs from `backend/requirements-ocr.txt`:

- `onnxruntime`, `optimum[onnxruntime]`, `transformers`, `opencv-python-headless`

First OCR request downloads ~1 GB TexTeller weights (or pre-cache with `download_texteller.bat`).

### 4.2 GPU (RTX — recommended)

```bat
scripts\install_ocr.bat
pip uninstall onnxruntime -y
pip install onnxruntime-gpu
scripts\download_texteller.bat
```

Set (optional):

```bat
set OCR_ONNX_DEVICE=auto
```

Restart the API after install.

**Verify:**

```http
GET http://localhost:8000/api/math/ocr/status
Authorization: Bearer <token>
```

Expect `"execution_provider": "CUDAExecutionProvider"` after first OCR load (or `"CPUExecutionProvider"` if GPU unavailable).

### 4.3 Force CPU only

```bat
set OCR_ONNX_DEVICE=cpu
```

---

## 5. Run dev & test OCR in browser

```bat
run.bat
```

| Page | URL |
|------|-----|
| Recognize test | http://localhost:5173/math-tutor/recognize-test |
| Train playground | http://localhost:5173/math-tutor/train |
| Practice + tutor | http://localhost:5173/math-tutor/practice/{topicId} |

Draw → idle OCR fires → LaTeX appears. Train playground **Confirm** / **Correct** writes to `data_logs/DSC_handwriting_dataset.csv`.

---

## 6. Verify build (pytest + frontend)

```bat
.venv\Scripts\activate
pytest tests/test_math_ocr.py tests/test_retrain_service.py tests/test_stroke_symbol_retrain.py tests/test_structure_calibrate.py tests/test_line_detect_structure.py -q
npm run build
```

Core math OCR tests should pass (some skip if TexTeller weights not loaded).

---

## 7. Improve accuracy — operator workflow

Run after collecting handwriting samples in Train Playground.

### Step A — Collect data

1. Open `/math-tutor/train`
2. Write each prompt; let OCR predict
3. **Confirm** (correct) or **Correct** (fix LaTeX)
4. Each sample saves:
   - PNG → `data_logs/training/{uuid}.png`
   - paths → `data_logs/training/{uuid}.paths.json`
   - row → `data_logs/DSC_handwriting_dataset.csv`

Intervention corrections also append to the same CSV (PNG only; no paths unless from train flow).

### Step B — Retrain stroke disambiguator (≥3 samples with paths)

```bat
scripts\retrain_stroke_symbol.bat
```

Or:

```http
POST /api/math/train/retrain-stroke-symbol?min_samples=3
```

### Step C — Recalibrate structure verify (≥5 samples or uses fixtures)

```bat
scripts\recalibrate_structure.bat
```

Or:

```http
POST /api/math/train/recalibrate-structure?min_samples=5
```

### Step D — TexTeller export (≥50 samples default)

```bat
scripts\retrain_texteller.bat
```

Output: `data/math/texteller_finetune/train/`

### Step E — Optional full TexTeller fine-tune (GPU + PyTorch)

```bat
git clone https://github.com/OleehyO/TexTeller vendor\TexTeller
pip install texteller[train]
set TEXTELLER_TRAIN_REPO=C:\path\to\Cognitive-Aware Learning Tutor\vendor\TexTeller
python scripts\retrain_texteller.py --mode train
```

After training, ONNX export / model swap is **manual** (not automated yet).

### Step F — Restart API

Restart backend so loaded ONNX sessions and threshold JSON reload.

---

## 8. Data & artifact paths

| Path | Contents |
|------|----------|
| `data_logs/DSC_handwriting_dataset.csv` | All confirmed/corrected labels |
| `data_logs/DSC_Kinematics.csv` | Per-stroke metrics from training |
| `data_logs/training/*.png` | Ink snapshots |
| `data_logs/training/*.paths.json` | Stroke paths for retrain |
| `data/math/stroke_symbol_model.npz` | Disambiguator weights |
| `data/math/structure_thresholds.json` | Calibrated geometry thresholds |
| `data/math/texteller_finetune/` | TexTeller export bundle |
| `models/texteller/` | Optional cached HF weights |

---

## 9. Troubleshooting

| Symptom | Fix |
|---------|-----|
| OCR status `texteller_available: false` | Run `scripts\install_ocr.bat` |
| Still on CPU with RTX | `pip install onnxruntime-gpu`; check CUDA driver; `OCR_ONNX_DEVICE=auto` |
| Retrain “insufficient samples” | More Train Playground confirms; need `paths_json_path` column filled |
| Stroke retrain skips rows | Same — paths only saved from train flow, not intervention-only rows |
| First OCR slow (~minutes) | Normal — TexTeller ~1 GB download |
| `parse_latex` errors on Python 3.14 | Known SymPy/ANTLR fragility; incomplete-step flag still works |
| Admin 403 on retrain APIs | Requires admin user JWT |

---

## 10. What is still deferred

- Production-grade OCR accuracy pass ([CANVAS_OCR_ROADMAP.md](../../CANVAS_OCR_ROADMAP.md))
- Auto-deploy fine-tuned TexTeller ONNX into live OCR
- WebGazer gaze + real EEG in stuckness (simulated today)
- Stroke-sequence symbol classifier trained on MathWriting (research prototype in
  `scripts/experiments/mathwriting_symbol_proto.py`). The bulk **importer** is a
  different thing and already shipped in Phase B as
  `backend/math/mathwriting_import.py` / `POST /api/math/train/import`; it is
  written and tested but has not been run against a live excerpt yet.

---

## 11. Quick reference — scripts

| Script | Purpose |
|--------|---------|
| `run.bat` | Start frontend + backend |
| `scripts\setup.bat` | Refresh deps after pull |
| `scripts\install_ocr.bat` | OCR pip stack |
| `scripts\download_texteller.bat` | Pre-download TexTeller weights |
| `scripts\retrain_stroke_symbol.bat` | Real-ink disambiguator |
| `scripts\recalibrate_structure.bat` | Geometry thresholds |
| `scripts\retrain_texteller.bat` | CSV → TexTeller export |

---

## 12. Export folder index

| Doc | Use |
|-----|-----|
| **This file** | Changes + build + run + retrain steps |
| [OCR_CLOSEOUT_2026-08-30.md](./OCR_CLOSEOUT_2026-08-30.md) | Short close-out summary |
| [MATH_OCR_ARCHITECTURE_EXPORT.md](./MATH_OCR_ARCHITECTURE_EXPORT.md) | Full architecture |
| [FILE_INDEX.md](./FILE_INDEX.md) | All related source files |
| [frontend/](./frontend/) | Source copy — React canvas |
| [backend/](./backend/) | Source copy — FastAPI math module |

**Initial export:** 2026-08-19 · **Last updated:** 2026-08-30
