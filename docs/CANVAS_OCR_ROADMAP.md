# Canvas & OCR — feature branch roadmap

Branch: `feat/math-canvas-ocr`

Current state on `main` is a **working scaffold**: tldraw canvas, TexTeller ONNX, train playground, and hallucination guards. Recognition quality is not production-ready (grid noise, contour fallback, sparse strokes).

## Goals

1. **Reliable OCR** — simple digits and equations (`3`, `x+2`) recognized consistently, not `\begin{array}` garbage.
2. **Canvas tuned for math** — export ink-only PNG (no grid), tight bounds, optional lined/sketch mode.
3. **Train loop** — curriculum prompts, sample logging, and eval against target LaTeX.

## Work items

### Canvas (frontend)

- [x] Export mode: ink-only PNG — `MathGridCanvas` draws on a transparent sketch layer; the ruled grid is a CSS overlay that never reaches exports
- [x] Fixed viewport: no zoom/pan on OCR pages (Train / Practice / Recognize use `MathGridCanvas`)
- [x] Restored `MathSplitWhiteboard` QoL in `MathGridCanvas`: pen/eraser, 5 colors, width sliders, undo/redo/clear/download, optional rough-work pane
- [x] Send `paths_json` (react-sketch-canvas CanvasPath[]) so backend `mask_from_paths()` isolates ink
- [x] Stroke analytics: `useStrokeAnalytics` + `strokeMetrics.ts` — per-stroke time/length/angles/grid-cell, session aggregates, `exportStrokeMetrics()`
- [x] Dynamic training layout: `grid_cells` highlighted character cells + ghost prompt, auto-clear on prompt advance, target-LaTeX match badge
- [ ] Canvas switcher: Grid (sketch) vs Board (tldraw) if both are needed (Study Room keeps tldraw)

### OCR (backend)

- [x] Grid suppression + crop (`ocr_service.py`)
- [x] Expand `_ocr_looks_hallucinated()` with real-world failure cases
- [x] Per-cell OCR rescue: when whole-canvas OCR is rejected, crop each training grid cell from stroke-metrics bboxes and concatenate (`_per_cell_ocr`)
- [x] Kinematics logging: `data_logs/DSC_Kinematics.csv` (one row per stroke) for train samples + interventions
- [x] Dataset extensions: `paths_json_path`, `target_latex`, `match_predicted` columns in `DSC_handwriting_dataset.csv`
- [ ] Improve contour digit classifier or drop it when TexTeller confidence is high
- [x] Ollama vision fallback wiring (`OLLAMA_VISION_MODEL` in `.env`)
- [x] Optional NIM teacher labels for training data (`use_nim_teacher`)
- [x] Golden tests: PNG fixtures → guarded LaTeX tiers (`tests/test_math_ocr.py`, `tests/test_stroke_metrics.py`)

### Dependencies

- `opencv-python` vs `opencv-python-headless` conflict breaks `face_tracker` GUI — document or split extras
- TexTeller cache: `scripts/download_texteller.bat`

## Verify

```bat
scripts\run_backend.bat
npm run dev
```

Manual acceptance checklist:

1. Train → draw `3` in 1 cell → Recognize → `3` (not `\begin{array}` noise)
2. Pen draws, eraser removes, no scroll-zoom on the canvas
3. Multi-cell prompt (e.g. `12`) → 2 cells highlighted, strokes-per-cell increments in the stats panel
4. Confirm a sample → rows appear in both `DSC_handwriting_dataset.csv` and `DSC_Kinematics.csv`
5. Practice intervention payload includes real `paths_json` (sketch canvas paths)
