# Math OCR — export folder

**Exported:** 2026-08-19 · **Updated:** 2026-08-30 (OCR close-out)  
**Purpose:** Review package for math canvas, OCR, SymPy grading, tutor, and training — frontend + backend.

| File / folder | Read this for |
|------|----------------|
| **[OCR_FULL_EXPORT.md](./OCR_FULL_EXPORT.md)** | **Master export** — BE + FE + architecture + plan + build (2026-08-30, incl. UniMERNet) |
| **[MATH_OCR_BUILD_AND_CHANGES.md](./MATH_OCR_BUILD_AND_CHANGES.md)** | **Start here** — build, run, retrain steps |
| **[OCR_TRAINING_DATA_POLICY.md](./OCR_TRAINING_DATA_POLICY.md)** | Editable vs permanent training data |
| **[OCR_RECOGNITION_ROADMAP.md](./OCR_RECOGNITION_ROADMAP.md)** | Proper math OCR — phased features |
| **[OCR_CLOSEOUT_2026-08-30.md](./OCR_CLOSEOUT_2026-08-30.md)** | **2026-08-30** — short close-out summary |
| **[MATH_OCR_ARCHITECTURE_EXPORT.md](./MATH_OCR_ARCHITECTURE_EXPORT.md)** | How it works, architecture, APIs, shipped vs deferred |
| **[FILE_INDEX.md](./FILE_INDEX.md)** | Every related source file (~55+) grouped by layer |
| **[frontend/](./frontend/)** | **Source copy** — canvas, pages, hooks, API client, widgets |
| **[backend/](./backend/)** | **Source copy** — full `backend/math/`, models, quiz handler, OCR deps |
| **[Math_Canvas_AI_Tutor_Architecture.pdf](./Math_Canvas_AI_Tutor_Architecture.pdf)** | **Blueprint doc** — north-star spec (mix of shipped + aspirational; see below) |

**Canonical in-repo docs (not duplicated here):**

- `docs/MATH_TUTOR_VISION_PIPELINE.md` — north-star loop + phases 3a–3d  
- `docs/CANVAS_OCR_ROADMAP.md` — canvas/OCR polish backlog  
- `docs/superpowers/specs/2026-08-08-math-multiline-ocr-tutor-design.md` — approved design  

**Install OCR stack:** `scripts/install_ocr.bat` · UniMERNet: `scripts/install_unimernet.bat`  
**Refresh source copies:** `python scripts/sync_math_ocr_export.py`

## Source copies in this folder (96 files, synced 2026-08-30)

```text
math-ocr/
  frontend/src/          ← React canvas, pages, mathClient, quiz OCR gate
  backend/math/          ← Full OCR module incl. UniMERNet + repair loop
  backend/models/        ← math.py, math_question.py
  backend/quiz/handler.py
  backend/integrations/nim_client.py
  scripts/               ← install, retrain, eval, sync
  tests/                 ← OCR unit tests
  *.md                   ← Architecture, build guide, full export
```

Paths mirror the repo so you can diff or hand off without cloning the whole project.
