# Canvas & OCR — feature branch roadmap

Branch: `feat/math-canvas-ocr`

Current state on `main` is a **working scaffold**: tldraw canvas, TexTeller ONNX, train playground, and hallucination guards. Recognition quality is not production-ready (grid noise, contour fallback, sparse strokes).

## Goals

1. **Reliable OCR** — simple digits and equations (`3`, `x+2`) recognized consistently, not `\begin{array}` garbage.
2. **Canvas tuned for math** — export ink-only PNG (no grid), tight bounds, optional lined/sketch mode.
3. **Train loop** — curriculum prompts, sample logging, and eval against target LaTeX.

## Work items

### Canvas (frontend)

- [ ] Export mode: white background, **no grid** in OCR snapshot (`isGridMode: false` during `toImage`)
- [ ] Tight shape bounds + minimum padding (already started in `TldrawMathCanvas`)
- [ ] Optional: restore `MathSplitWhiteboard` (react-sketch-canvas) for OCR-only pages — sends `paths_json` for ink masking
- [ ] Canvas switcher: Grid (sketch) vs Board (tldraw) if both are needed
- [ ] Send `paths_json` when available so backend `mask_from_paths()` isolates ink

### OCR (backend)

- [ ] Grid suppression + crop (started in `ocr_service.py`)
- [ ] Expand `_ocr_looks_hallucinated()` with real-world failure cases
- [ ] Improve contour digit classifier or drop it when TexTeller confidence is high
- [ ] Ollama vision fallback wiring (`OLLAMA_VISION_MODEL` in `.env`)
- [ ] Optional NIM teacher labels for training data (`use_nim_teacher`)
- [ ] Golden tests: PNG fixtures → expected LaTeX (no model download in CI)

### Dependencies

- `opencv-python` vs `opencv-python-headless` conflict breaks `face_tracker` GUI — document or split extras
- TexTeller cache: `scripts/download_texteller.bat`

## Verify

```bat
scripts\run_backend.bat
npm run dev
```

Math → Recognize Test: draw `3`, expect `3` or close LaTeX (not table/array noise).
