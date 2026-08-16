# Daily Practice — soft nudge (now) + tagged engine (later)

**Date:** 2026-08-09  
**Status:** Now = implement soft nudge (Approach 1 + choice A). Later = Option 3 engine (loved, not built yet).

## Locked choices

| Choice | Decision |
|--------|----------|
| After plan | Soft nudge only — day already open (A) |
| Ship now | Wire existing Review Hub + SRS + requeue |
| Not now | Hard Soft-land lock, productivity unlock points for quiz |
| Future | Full tagged Daily Practice engine (Option 3) |

## Now — soft nudge

### Flow

```text
Plan confirmed / blocks on calendar
  → morning.next = open (unchanged)
  → UI: “Daily practice” CTA → /review?tab=due (or vocab read if that is next_step)
  → Jarvis: one rate-limited nudge when due_count > 0 (after plan praise)
  → Wrong → session requeue; correct/wrong → FSRS (existing)
```

### Payload

`morning.daily_practice` on distraction gate:

- `due_count`, `label`, `to`, `action` (from `compute_next_step` / backlog)
- Shown only as a hint — never blocks Soft-land

### Out of scope (now)

- Per-tag quotas, new session orchestrator, new DB tables
- Vocab read→quiz rewrite (keep GRE path; CTA may deep-link)

---

## Later — Option 3: tagged Daily Practice engine

**Intent:** One “Start Daily Practice” workout that *plans* today’s mix, not only opens the due pile.

| Piece | Behavior |
|-------|----------|
| Quota planner | Morning targets: e.g. 8 vocab + 6 math + 10 study, from due + weak tags + goals |
| Tag partitions | Lanes: `vocab`, `math`, `numpy`, `pandas`, … (tags under `study` / math) |
| Orchestrator | Ordered run: vocab read→quiz → math → notes/manual |
| Learn-until-right | In-session retry stack until correct, then FSRS |
| Progress | Lane checklist / streak; optional soft goal (B) later — still no hard gate unless chosen |
| Sources | Vocab bank, math skills, notes quizzes, manual cards — one tagged queue |

**Depends on:** stable tags on `ReviewCard` / decks; soft nudge habit proven.

**Do not start Option 3 until** soft nudge is live and user asks to build the engine.
