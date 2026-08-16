# Future plan: Tagged Daily Practice engine (Option 3)

**Status:** Deferred — revisit when soft nudge habit is proven.  
**Not started.** Soft nudge (Approach 1 + A) is what ships today.  
**Related:** [2026-08-09-daily-practice-soft-nudge-design.md](./superpowers/specs/2026-08-09-daily-practice-soft-nudge-design.md)

## Why this exists

User preference: love Option 3 long-term; ship soft Review Hub nudge first. Keep this note **separate** so Option 3 is easy to find without digging soft-nudge work.

## Product intent

One **Start Daily Practice** workout that *plans* today’s mix (not only opens the due pile).

```text
Morning / after plan
  → Quota planner (vocab + math + tagged study)
  → Ordered lanes (read→quiz → math → notes/manual)
  → Wrong → retry until correct → FSRS
  → Lane progress / optional soft goal later
```

## Engine pieces

| Piece | Behavior |
|-------|----------|
| **Quota planner** | Daily targets from due counts, weak tags, and goals (e.g. 8 vocab + 6 math + 10 study) |
| **Tag partitions** | Lanes: `vocab`, `math`, `numpy`, `pandas`, … (tags under study/math) |
| **Orchestrator** | Single session walks lanes in order |
| **Learn-until-right** | In-session requeue until correct, then FSRS across days |
| **Progress** | Lane checklist / streak; optional soft goal (points) without Soft-land lock unless chosen later |
| **Sources** | Vocab bank, math skills, notes quizzes, manually added cards — one tagged queue |

## Explicitly out until revisit

- Hard Soft-land lock for quiz quota (choice C)
- Parallel quiz DB / second SRS system
- Replacing GRE read→quiz path (engine should *call* it, not fork it)

## When to build

- Soft nudge is live and used for a while, **and**
- User asks to start Option 3 (or a completion-sprint item points here)

## First implementation slice (when greenlit)

1. Spec + ADR: tag model on `ReviewCard` / decks  
2. `POST /api/quiz/daily-practice/start` quota + ordered queue  
3. Minimal lane UI on `/review` (or dedicated page)  
4. Wire vocab read→quiz as first lane when vocab due  

## Index

Also listed under [docs/FUTURE_VISION.md](./FUTURE_VISION.md) → Study loop / Daily Practice.
