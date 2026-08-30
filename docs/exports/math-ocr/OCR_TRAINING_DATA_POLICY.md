# OCR training data — editable vs permanent

**Updated:** 2026-08-30

---

## Recommendation: **editable + deletable** (not permanent)

| Approach | Pros | Cons |
|----------|------|------|
| **Permanent append-only** | Simple audit trail | Bad labels never leave → poisons retrain |
| **Editable + deletable (chosen)** | Fix typos, remove mis-clicks, curate quality | Must re-run export/retrain after edits |

Training data is **not** sacred history — it is **fuel for models**. Wrong LaTeX on a PNG is worse than no sample.

### What we keep

- CSV row + PNG + `paths.json` per sample
- Soft edits: change `confirmed_latex` without re-drawing
- Hard delete: remove row + files (irreversible)

### What we do not do (yet)

- Version history / undo stack
- Archive tombstone table (could add later)

---

## Two UI surfaces

| Page | Route | Role |
|------|-------|------|
| **Train Playground** | `/math-tutor/train` | Collect new samples (curriculum prompts) |
| **OCR training data** | `/math-tutor/training-data` | Review, edit labels, delete, trigger retrain |

---

## API

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/math/train/samples` | List your samples |
| GET | `/api/math/train/samples/{id}` | One sample |
| GET | `/api/math/train/samples/{id}/image` | PNG preview |
| PATCH | `/api/math/train/samples/{id}` | Edit label / metadata |
| DELETE | `/api/math/train/samples/{id}` | Delete sample + files |

Admin: `GET /train/samples?all_users=true`

---

## After edit or delete

Re-run as needed:

1. `scripts\retrain_stroke_symbol.bat`
2. `scripts\recalibrate_structure.bat`
3. `scripts\retrain_texteller.bat` (when ≥50 samples)

Edits do **not** auto-retrain — you control when models refresh.
