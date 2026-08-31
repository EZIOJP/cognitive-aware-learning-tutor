# Math OCR — parked 2026-08-31, resume here

Architecture and guardrails are done and committed. **Nothing is blocked on code.**
The blocker is that there is almost no training data yet.

Commits: [`bd21c0b`](https://github.com/EZIOJP/cognitive-aware-learning-tutor/commit/bd21c0b)
(dual-engine OCR lane) and
[`a4ba4e6`](https://github.com/EZIOJP/cognitive-aware-learning-tutor/commit/a4ba4e6)
(training guardrails).

---

## The actual state of the dataset

```
python scripts/eval_ocr_baseline.py --split all --distribution-only
```

As of 2026-08-31 this prints:

```
split=all rows=5
  tiers: {'digits': 4, 'quiz': 1}
  5 distinct labels: 'o', '2x+5=0', '0', '\underset{o}{o}', '48'
```

Five samples, **one** of which has `paths_json` (stroke data). Structure calibration
reports `real_count: 1`, `skip_reasons: {missing_paths_json: 4}`.

Every retrain threshold in the system is far above this. Collecting samples is step one;
everything else is downstream of it.

---

## TODO, in dependency order

- [ ] **Collect ~50 confirmed samples in Train Playground.** Only samples saved with
      stroke data count toward structure calibration. Four of the five existing rows
      have no `paths_json`, so check that the save path is actually capturing strokes
      before doing a long collection session — otherwise you will collect 50 unusable rows.
- [ ] **Check class balance** with `--distribution-only` before training anything. Watch
      `labels_seen_once` and `top_label_share`. Fifty rows that are forty copies of one
      expression teaches nothing.
- [ ] **Freeze the holdout and record a baseline** once there is enough data:
      ```
      curl -X POST .../api/math/train/holdout/freeze
      python scripts/eval_ocr_baseline.py --label pre-finetune
      ```
      Do this *before* the first retrain or there is nothing to compare against.
- [ ] **Bulk-import MathWriting** (`POST /api/math/train/import`, or run
      `backend/math/mathwriting_import.py`). The dedupe bug is fixed, so re-running is
      now safe and diversity is preserved. **This has still never been run against a
      live excerpt** — expect first-run surprises.
- [ ] **Eyeball both image sources side by side** before mixing them. MathWriting
      rasterizes to a fixed 400x120 canvas at 3px stroke width; your canvas PNGs come
      from a live canvas at whatever size and width you drew with. If they look
      obviously different, the model can learn the difference as a shortcut instead of
      learning handwriting.
- [ ] **Retrain stroke symbol**, then **recalibrate structure**. Calibration now needs
      8 real samples and refuses to run on synthetic fixtures alone.
- [ ] **Smoke-test the TexTeller training environment** with a tiny 5-sample, 1-epoch run
      before committing to a real fine-tune. `TEXTELLER_TRAIN_TIMEOUT_SEC` defaults to
      7200s and Python 3.14 + PyTorch is unverified here.
- [ ] **Fine-tune with a low learning rate and few epochs.** `train_config.yaml` defaults
      are tuned for training from scratch, not a small personalization pass. Watch
      holdout accuracy each epoch and stop when it stops improving.
- [ ] **Confirm CUDA** via `GET /api/math/ocr/status` — `execution_provider` should say
      CUDA, not CPU.

---

## What the guardrails do (so you do not fight them)

| Guardrail | Behavior | Where |
|---|---|---|
| Holdout split | `sha1(sample_id) % 1000 < fraction*1000`, default 20%. Stable as data grows — a sample never migrates between splits. | `backend/math/holdout.py` |
| Export | Held-out rows go to `val/`, never `train/`. `min_samples` is checked against the **trainable** count. | `retrain_service.py` |
| Calibration floor | Needs 8 real samples with `paths_json`. Synthetic fixtures do not count. | `structure_calibrate.py` |
| Synthetic weight | Decays `1.5 x 8/(8+real)`. Fixtures stop outvoting real ink past ~8 samples. | `_synthetic_weight` |
| MLP gate | Needs 30 real samples, trains on real ink only. | `_train_structure_mlp` |
| Snapshots | Thresholds, both `.npz`, and the export manifest are copied before overwrite; last 5 kept in `data/math/artifact_snapshots/`. `restore_latest()` rolls back. | `artifacts.py` |

Regression tests for all of this: `tests/test_ocr_training_guardrails.py`.

---

## Known issues left open

**The structure MLP is circular.** Its training targets come from `verify_structure`,
the same heuristic it is supposed to augment, and its output feeds back into that
heuristic's confidence. It can only ever imitate, never correct. It is gated at 30 real
samples so it cannot do damage, but to make it genuinely useful the labels need to come
from human confirm/reject decisions instead. Not urgent, but do not expect accuracy
gains from it as built.

**Calibration's fit score is self-referential.** `score_before`/`score_after` are
measured on the same samples the grid search maximized over. Only `holdout_score_before`
/ `holdout_score_after` in the report mean anything. This is now labelled in the report's
`note` field.

**MathWriting is CC BY-NC-SA 4.0.** Fine for personal use. A checkpoint fine-tuned on it
inherits the non-commercial restriction — relevant only if this ever ships as a product.

**Doc drift, now fixed but worth knowing:** `mathwriting_import.py` (the working bulk
importer, Phase B) and `scripts/experiments/mathwriting_symbol_proto.py` (a research
stroke classifier) are different things with confusingly similar names. Two close-out
docs listed the importer as deferred when it had already shipped.

---

## Unrelated pre-existing failure

`tests/test_llm_test_profiles.py` fails with `ModuleNotFoundError: No module named 'huey'`.
It is the LLM job queue, nothing to do with OCR. Either `pip install huey` or leave it.
