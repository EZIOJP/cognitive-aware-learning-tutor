# Math Daily Path — Scratch → Graduate

**Status:** bank structured · **2,884** items · **48** topics · every pack on curriculum  
**Tags:** lectures `L{n}-Txx` · math `MT{n}-Txx`

## What’s imported (yes)

| Layer | Sources | ~Qs | Difficulty |
|-------|---------|-----|------------|
| Easy drill | DeepMind + mathgenerator | ~970 | foundations |
| Interview quant | SAT + MathQA + SAKET + authored T07 | ~1,294 | foundations |
| Competition | Hendrycks MATH | 320 | core / stretch |
| Olympiad | MathNet (EN, answer-bearing) | 300 | advanced |

**Remaining thin spots:** `MT4`–`MT6` notes still skeleton; calculus bank is tiny (MathNet). Coding kind under `data/questions/coding/` not started yet.

---

## Levels (unlock in order)

Do **Daily Path** = Read note section → Practice tagged questions → fail → Review Hub (SRS).  
**Pass rule:** ≥80% on a 15-question set, then unlock next.

### L0 — Warm-up (1–2 weeks)

| Order | Tag | Practice packs |
|-------|-----|----------------|
| 1 | `MT1-T01` | DeepMind arith + roots + primes + mathqa-other |
| 2 | `MT1-T02` | DeepMind GCD/LCM + gen-lcm/gcd/common-factors |

### L1 — Interview quant core (3–5 weeks)

| Order | Tag | Practice packs |
|-------|-----|----------------|
| 3 | `MT1-T03` | mathqa-general + gen-percentage |
| 4 | `MT1-T04` | sat-algebra |
| 5 | `MT1-T05` | sat-data |
| 6 | `MT1-T06` | mathqa-physics |
| 7 | `MT1-T07` | **authored time-work** |
| 8 | `MT1-T08` | mathqa-gain + gen-profit-loss |
| 9 | `MT1-T09` | gen-interest |
| 10 | `MT1-T10` | gen-combinations/permutations |
| 11 | `MT1-T11` | mathqa-probability + DeepMind prob + dice |
| 12 | `MT1-T12` | gen-ap/gp only (progressions) |
| 13 | `MT1-T14` | sat-geometry + mathqa-geometry |
| 14 | `MT1-T13` | saket coding aptitude (optional) |

### L2 — Algebra bridge

| Order | Tag | Practice packs |
|-------|-----|----------------|
| 15 | `MT2-T01` | sat-advanced + DeepMind linear + gen-algebra |
| 16 | `MT2-T02` | hendrycks algebra + MathNet algebra |

### L3 — AI/ML math entry

| Order | Tag | Practice packs |
|-------|-----|----------------|
| 17 | `MT3-T01` | aiml vector-dot/cross |
| 18 | `MT4-T01` | MathNet calculus (**notes first**) |

### L4 — Stretch (optional)

MathNet geometry/number/mixed + Hendrycks prealgebra / number theory / counting.

---

## Folder structure (canonical)

```text
data/notes/math/              # MT notes (read)
data/questions/math/
  aptitude/   sat | mathqa | saket | authored
  generated/  mathgenerator
  deepmind/   DeepMind school modules
  aiml/       vector drills
  competition/ Hendrycks
  olympiad/    MathNet
  curriculum.json
```

Machine-readable unlock order: `data/questions/math/curriculum.json`.

---

## How to study one day

1. Open next unlocked `MT` section in notes  
2. Practice **10–20** questions with that `note_topic_ids` tag (easy first)  
3. Wrongs → Review Hub due cards  
4. Don’t jump to MathNet until L2 feels boring  

Curriculum English pass (map/tag/stubs; no wipe by default):

```bat
python scripts/math_en_curriculum_pass.py --skip-seed
python scripts/math_en_curriculum_pass.py
```

Legacy full re-import (destructive `--clean-out` — avoid for curated empties):

```bat
python scripts/import_math_aptitude_datasets.py --clean-out
python scripts/structure_math_questions.py
```
