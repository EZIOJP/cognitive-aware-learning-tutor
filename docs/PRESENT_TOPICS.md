# Present topics — reference catalog

**Live inventory** of Study Loop / quiz topic IDs currently in this repo.  
Update this when you add a note Topic Index row or a `curriculum.json` step.

Sources: `data/questions/math/curriculum.json` · `data/notes/**` Topic Indexes · Math Core worksheets.

---

## Math — Daily Path (`MT*`)

### L0 — Warm-up

| # | ID | Title |
|---|-----|--------|
| 1 | `MT1-T01` | Number systems & divisibility (**Math Core** daily must) |
| 2 | `MT1-T02` | LCM & HCF |

**Math Core read cards** (same notes file; not separate curriculum steps) — **`MT0` basics first**:

| ID | Title |
|----|--------|
| `MT1-T01` | Number systems & divisibility (optional skim) |
| `MT0-T01` | Math Core · tables 2–25 |
| `MT0-T02` | Math Core · primes & factorization |
| `MT0-T03` | Math Core · fraction ↔ % |
| `MT0-T04` | Math Core · squares |
| `MT0-T05` | Math Core · cubes |
| `MT0-T06` | Math Core · powers |
| `MT0-T07` | Math Core · calculation shortcuts |
| `MT0-T08` | Math Core · unit conversions |
| `MT0-T09` | Math Core · approximation & estimation |

*(Legacy ids `MT1-T16`…`T24` still resolve to the matching `MT0-Txx`.)*

### L1 — Interview quant core

| # | ID | Title |
|---|-----|--------|
| 3 | `MT1-T03` | Percentages |
| 4 | `MT1-T04` | Ratio & proportion |
| 5 | `MT1-T05` | Averages & mixtures |
| 6 | `MT1-T06` | Time, speed & distance |
| 7 | `MT1-T07` | Time & work |
| 8 | `MT1-T08` | Profit, loss & discount |
| 9 | `MT1-T09` | Simple & compound interest |
| 10 | `MT1-T10` | Permutations & combinations |
| 11 | `MT1-T11` | Probability |
| 12 | `MT1-T12` | Progressions |
| 13 | `MT1-T14` | Geometry & mensuration |
| 14 | `MT1-T13` | Programming aptitude *(optional)* |

### L2 — Algebra bridge

| # | ID | Title |
|---|-----|--------|
| 15 | `MT2-T01` | Linear & quadratic |
| 16 | `MT2-T02` | Competition algebra |

### L3 — AI/ML math entry

| # | ID | Title |
|---|-----|--------|
| 17 | `MT3-T01` | Vectors for ML |
| 18 | `MT4-T01` | Calculus for ML |

### L4 — Olympiad / competition stretch *(optional)*

| # | ID | Title |
|---|-----|--------|
| 19 | `MT1-T14` | Olympiad geometry |
| 20 | `MT1-T01` | Number theory / prealgebra stretch |
| 21 | `MT1-T11` | Competition counting & probability |
| 22 | `MT2-T02` | MathNet mixed |

Notes file: `data/notes/math/MT1_aptitude_interview_notes.md` (MT1 index).  
Other MT modules: add Topic Index rows in their module notes when authored.

---

## Lectures — Data foundations (`L*`)

Present note files with Topic Index (quiz-ready IDs):

| Lecture | Note file | Topic IDs present |
|---------|-----------|-------------------|
| L2 | (numpy / indexing notes in tree) | `L2-T02` … |
| L3 | `L03_numpy_lecture3_notes.md` | `L3-T02` … |
| L4 | `L04_vectorization_stacking_pandas_notes.md` | `L4-T02` … `L4-T38` |
| L5 | `L05_pandas_operations_notes.md` | `L5-T01` … `L5-T17` |

Open the file’s **Topic Index** table for the full numbered list (ID · Topic · one-line scope).

---

## Vocab

| Pattern | Example | Where |
|---------|---------|--------|
| GRE group | `vocab.group.N` | Flash decks / Study Loop tag stitch |

---

## Related scales (not topic IDs)

| System | Values | Purpose |
|--------|--------|---------|
| **Importance** | 1–5 (default 3) | Mastery bar + FSRS density; daily bite ranking |
| **Difficulty ladder** | easy → medium → hard → advanced | Which **packs** inside an MT tag you get |

Importance UI: Review Hub → Flash decks → **Imp** per tag.  
Difficulty: Study Loop practice on MT tags (`topic_level.py`).

---

## Quick copy — Math Core + MT1 IDs

```
MT1-T01                         ← warm-up / daily practice tag
MT0-T01  MT0-T02  MT0-T03       ← tables → primes → fraction%
MT0-T04  MT0-T05  MT0-T06       ← squares → cubes → powers
MT0-T07  MT0-T08  MT0-T09       ← shortcuts → units → estimation
MT1-T02 … MT1-T14               ← interview quant
```
