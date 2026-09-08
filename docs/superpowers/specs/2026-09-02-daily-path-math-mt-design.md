# Daily Path + Math Topics (MT) — Design

**Date:** 2026-09-02  
**Status:** approved (owner: “whatever you think is best”)  
**Related:** ADR-001 (one `/api/quiz` + FSRS ReviewCards), `docs/QUESTION_CONTENT_FORMAT.md`, `docs/superpowers/specs/2026-07-17-mental-math-aptitude-design.md`

## Goal

Wipe weak/inferior practice state, then grow **math aptitude (interview)** and **AI/ML math** the right way:

1. Notes first (roadmap + skeletons, then deepen)
2. Questions next (bank early for aptitude; generate/import slowly for harder ML math)
3. **Daily Path** — forced read → practice, with low-mastery items in spaced repetition

## Activity name: Daily Path

**Daily Path** = the day’s guided block:

```text
Read (MT / L topic notes) → Practice (MCQ / math / coding) → Review weak (FSRS due)
```

- **Path** = today’s assigned topic(s) you must read before unlocking that topic’s practice set  
- **Review Hub** keeps owning spaced repetition for low mastery / failed items (not a second SRS)  
- UI copy: “Start Daily Path”, “Continue Path”, “Due for review”

## Tag scheme

| Domain | Tag shape | Example |
|--------|-----------|---------|
| Lecture notes | `L{n}-Txx` | `L5-T03` |
| Math notes / questions | `MT{n}-Txx` | `MT1-T07` |

**Math modules (`MT{n}`):**

| Module | Track | Scope |
|--------|-------|--------|
| MT1 | Aptitude / interview quant | LCM/HCF, %, ratios, averages, TSD, work, P&L, SI/CI, P&C, probability basics, number systems |
| MT2 | Algebra & functions | equations, inequalities, functions, logs/exponentials |
| MT3 | Linear algebra for ML | vectors, matrices, norms, eigendecomp intuition |
| MT4 | Calculus for ML | derivatives, gradients, chain rule, multivariable basics |
| MT5 | Probability & stats for ML | Bayes, distributions, expectation, estimation |
| MT6 | Optimization & ML math | GD, convexity lite, loss landscapes |

Notes headings use the same pattern as lectures:

```markdown
## Topic Index
- `MT1-T01` — LCM & HCF

## `MT1-T01` — LCM & HCF
```

Questions in `data/questions/` set `topic.topic_id` to the MT id (or keep slug + `note_topic_ids: ["MT1-T01"]`).

## Phased delivery

### Phase 0 — Wipe (now)

Clear inferior practice artifacts for the signed-in user (or all local users via script):

- `quiz_decks`
- `review_cards`
- open/completed `quiz_sessions` used by global practice

**Keep:** GRE word bank, lecture notes files, vocab definitions.  
After wipe, Review Hub shows empty until Daily Path / import / generate reseeds cards.

### Phase 1 — Hybrid notes

1. **One-shot:** write `docs/MATH_ROADMAP.md` + skeleton notes under `data/notes/math/` (MT1…MT6 topic index + short stubs).  
2. **Continuous:** deepen one MT topic at a time (full pedagogy: what it is → rules → examples → pitfalls).

### Phase 2 — Questions (aptitude-heavy first)

- **MT1:** large authored/generated bank early (tons of interview-style math is fine and useful).  
- **MT2–MT6:** smaller high-quality sets; grow via generate/import.  
- Kinds: `math` (SymPy), `mcq`, later `coding` where NumPy illustrates the math.  
- Mental-math ladder (`2026-07-17-mental-math-aptitude-design.md`) sits under MT1 as a speed/skills lane (dynamic gen OK); word problems prefer the content bank.

### Phase 3 — Daily Path product

- Pick next unread/unlocked MT (or L) topic  
- Gate: mark read (or dwell) → unlock practice pack  
- Failures → ReviewCards due sooner  
- Dashboard: “Daily Path” + “Review N due”

## Non-goals (this lane)

- Graphical Mermaid editor  
- Renaming `/api/quiz` internals (user-facing label “Questions” / “Daily Path” only)  
- Second SRS engine

## Success criteria

- Wipe leaves zero decks/cards for practice domains; vocab words intact  
- MT tags parse like L tags  
- At least MT1 skeleton notes + a starter aptitude question set  
- Daily Path can assign “read MT1-Txx → N questions” and weak items appear in Review Hub
