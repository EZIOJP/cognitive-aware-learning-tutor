# Phase 0 results — multi-line math OCR validation

**Date:** 2026-08-08
**Spec:** [2026-08-08-math-multiline-ocr-tutor-design.md](2026-08-08-math-multiline-ocr-tutor-design.md) §4 Phase 0
**Machine:** Windows, 8 physical / 16 logical cores, Python 3.14.4 (`.venv`), ~300 GB free disk
**Scripts:** `scripts/experiments/phase0_*.py` (outputs in `scripts/experiments/out/`)

Environment note: all OCR deps from `requirements-ocr.txt` were already installed
(onnxruntime 1.26, optimum 2.1 + optimum-onnx 0.1, transformers 4.57, opencv 4.13),
and the TexTeller model was already in the HF cache — nothing new was installed
into the venv for these experiments. Test images are **synthetic printed math**
(matplotlib mathtext), not handwriting — treat absolute accuracy numbers as an
upper bound; latency numbers should transfer.

---

## Experiment 1 — TexTeller latency + ONNX thread tuning

`phase0_exp1_latency.py`, 10 timed runs (after 1 warmup) on a single-line
"2x + 3 = 7" image, each mode in a fresh process. Tuned = `ORT_SEQUENTIAL` +
`intra_op_num_threads=8` (physical cores) + `session.intra_op.allow_spinning=0`,
passed via `session_options=` to `ORTModelForVision2Seq.from_pretrained`
(optimum 2.1 accepts the kwarg directly — no provider_options workaround needed).

| Config | p50 | p90 | min | max | Output |
|--------|-----|-----|-----|-----|--------|
| Default | 0.749 s | 0.763 s | 0.717 s | 0.780 s | `2x+3=7` ✅ |
| Tuned | 0.735 s | 0.750 s | 0.706 s | 0.767 s | `2x+3=7` ✅ |

- **p50 ≈ 0.75 s/line — well under the 1.5 s go threshold**, even untuned.
- Tuning gained only ~2% here; low variance either way. Worth applying the
  no-spinning option in `texteller_onnx.py` anyway (frees cores for the FastAPI
  process during idle; zero cost), but it is not a latency lever on this box.
- Model load: 14–35 s per process (one-time; the backend keeps it in `lru_cache`).
- Longer lines cost more (autoregressive decode): the 3-line whole-image run in
  Exp 3 took 1.25–2.1 s, single crops with fractions/integrals 0.75–0.95 s.

## Experiment 2 — MFD / pix2text feasibility on Python 3.14

**pix2text pip install now resolves on 3.14** — this changed since the spec was
written. `pip install --dry-run pix2text` (no venv modification) resolved
pix2text 1.1.6 successfully; the old blocker is gone (stringzilla 5.1.1 now ships
a cp314 wheel). The dry-run "would install" list contains **~30 new packages**
(ultralytics, pytorch-lightning, wandb, cnocr, cnstd, doclayout-yolo, rapidocr,
seaborn, polars, sentry-sdk…) and **no upgrades/downgrades of existing packages**.
So it's installable — but it's several hundred MB of dependency bloat for one
80 MB detector, and pip resolution ≠ proven runtime health of cnstd/cnocr on 3.14.
Not installed; not recommended.

**Direct MFD ONNX with plain onnxruntime: confirmed easy** (`phase0_exp2_mfd_probe.py`).
Downloaded `breezedeus/pix2text-mfd-1.5` (single 80 MB ONNX file, now in HF cache):

- Loads in an ORT session with zero extra deps (session load 0.3 s).
- Input `images` `[batch, 3, H, W]` float32, dynamic size; output `[1, 6, N]` —
  standard YOLOv8 layout: 4 box coords + 2 class scores (embedded / isolated formula).
- Raw inference **~0.23 s at 768×768** on CPU (3 runs: 0.238/0.234/0.232) —
  inside the spec's 100–300 ms MFD budget.
- Remaining effort for real use: letterbox-resize preprocessing + score filter +
  xywh→xyxy + NMS ≈ 50 lines of numpy. **Estimate: ~half a day** for a
  `mfd_onnx.py` with tests.

**Stroke Y-gap fallback:** `strokeMetrics.ts` already computes per-stroke
`bbox {x,y,w,h}` plus grid cell and timing. Clustering strokes into lines by
vertical bbox overlap/gap is straightforward and needs no model — it's the
vector-space twin of the projection profile below, and additionally survives
overlapping descenders (uses stroke identity, not pixel rows). Limitation: only
works for canvas input with `paths_json`, not imported images; and side-by-side
work (two columns) needs an extra X-split pass. Covers the primary canvas UX fine.

## Experiment 3 — Multi-line segmentation + per-line OCR

`phase0_exp3_segment.py` on 5 synthetic stacked-equation images (2–3 lines,
vertical gaps 12–60 px, incl. fractions and integrals). Naive horizontal
projection profile: Otsu binarize → sum ink per row → split on ≥8 empty rows.

| Sample | Lines | Detected | Split | Seg time | Per-line OCR |
|--------|-------|----------|-------|----------|--------------|
| 3-line gap 30 | 3 | 3 | ✅ | 7.7 ms | all correct |
| 3-line gap 12 | 3 | 3 | ✅ | 0.5 ms | all correct |
| 3-line gap 60 | 3 | 3 | ✅ | 0.7 ms | all correct |
| 2-line quadratic gap 25 | 2 | 2 | ✅ | 0.6 ms | all correct |
| 3-line calculus gap 35 | 3 | 3 | ✅ | 13.1 ms | 1 digit error* |

\* Crop of `y = x^{3} + 1` read as `y=x^{3}+2`; the whole-image pass read the
same line correctly — a reminder that tight crops can hurt, keep some padding.

**Segmentation: 5/5 correct, < 15 ms — go criterion met.** Per-line OCR
0.64–0.95 s/crop.

Per-line vs whole-image TexTeller (unexpected finding): TexTeller can natively
emit multi-line output as `\begin{array}{l} … \\ … \end{array}` — the three
3-line samples came back complete and correct from a single whole-image call in
1.25–2.1 s (faster than 3 separate crop calls). **But it silently dropped the
entire second line** of the 2-line quadratic sample (returned only
`x^{2}-5x+6=0`). Whole-image is a usable fallback, not a reliable primary —
silent line loss is exactly the failure mode the tutor can't detect.

## Experiment 4 — Whole-canvas vision model (Ollama)

**Skipped: Ollama is not installed on this machine** (nothing on
`localhost:11434`, no `ollama` binary in PATH or the standard install dirs, no
`~/.ollama`). Not installed as part of this experiment (app install is a
system-level change beyond Phase 0 scope).

To run this later: install Ollama, then `ollama pull qwen2.5vl:7b` (~6 GB;
alternatives `minicpm-v` ~5.5 GB, `llava:7b` ~4.7 GB — all fit in the ~300 GB
free). Expect CPU-only VLM inference on a whole canvas to take tens of seconds —
very likely outside the < 2 s feedback budget — so this path only matters as an
accuracy benchmark or async background pass, not the hot path.

---

## Verdict vs go criteria: **GO**

| Criterion | Target | Measured | Result |
|-----------|--------|----------|--------|
| TexTeller p50 per line (tuned) | < ~1.5 s | 0.735 s (0.749 s untuned) | ✅ |
| 3-line samples split usefully | yes | 5/5 correct, < 15 ms | ✅ |

## Recommendation for Phase 1

**Primary: projection-profile heuristic** (pixel Y-gap) for `detect_formula_boxes`,
with generous crop padding (≥10 px). It's 5/5 on samples, < 15 ms, zero new
dependencies, and trivially debuggable. On canvas input, cross-check with stroke
bbox Y-clustering from `paths_json` (data already exists) to survive overlapping
ascenders/descenders in real handwriting.

**Second: MFD ONNX direct via onnxruntime** (~half-day effort, 80 MB, ~0.23 s) —
add when real handwriting shows the heuristic's limits (skewed lines, side-by-side
work, embedded formulas in text). Do **not** install the full pix2text package:
it now resolves on 3.14 but drags in ~30 packages (ultralytics/wandb/lightning)
for nothing we need.

**Whole-image TexTeller as fallback only** (it already emits `\begin{array}` for
stacked equations) — never primary, because it can silently drop lines.

**VLM path: defer.** Untestable today (no Ollama) and almost certainly too slow
on CPU for the hot path; revisit as an async accuracy benchmark if per-line
accuracy on real handwriting disappoints.

Also worth folding into Phase 1: apply `session.intra_op.allow_spinning=0` (+
sequential mode) in `texteller_onnx.py` via `session_options` — free politeness
win, confirmed compatible with the optimum 2.1 loader.
