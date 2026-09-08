# Generation rules — notes & per-topic quiz

Permanent rules for the CALT study webapp. Code mirror: `backend/transcripts/generation_rules.py`.

**Present topic catalog (reference):** [`docs/PRESENT_TOPICS.md`](PRESENT_TOPICS.md) — all current `MT*` / `L*` IDs in this repo.

## Topic ID format

| Format | Example | When |
|--------|---------|------|
| **Lecture canonical** | `L5-T05` | Lecture **5**, topic **05** (two-digit) |
| **Math fluency** | `MT0-T01` | Math Core basics (tables → estimation) |
| **Math interview** | `MT1-T01` | Math module **1**, topic **01** |
| Decimal fallback | `2.1` | Old notes without L/MT IDs |

Quiz walks lecture topics in numeric order. Math Study Loop is tag-scoped + difficulty-scoped.

When adding content: put the ID in the note **Topic Index**, add `## \`ID\` — title`, and (for math path) a `curriculum.json` step — then update `PRESENT_TOPICS.md`.

### Present topics (short)

Full tables → **[`PRESENT_TOPICS.md`](PRESENT_TOPICS.md)**.

**Math Core / MT1:** warm-up `MT1-T01` + fluency worksheets `MT0-T01`…`MT0-T09` (basics first) + interview `MT1-T02`…  
**Later math:** `MT2-T01` `MT2-T02` · `MT3-T01` · `MT4-T01`  
**Lectures:** `L3-*` `L4-T02…T38` `L5-T01…T17` (see each note’s Topic Index)  
**Vocab:** `vocab.group.N`

---

## Tag importance scale (1–5)

Editable per tag (`tag_importance.json`). UI: Flash decks → **Imp**. Default **3**.

| I | Bar | Interval factor | Meaning |
|---|-----|-----------------|---------|
| 1 | 2 | 1.25 | Low stakes |
| 2 | 3 | 1.0 | Light |
| 3 | 4 | 0.85 | Default |
| 4 | 5 | 0.70 | High stakes |
| 5 | 6 | 0.55 | Exam-critical |

Daily bite ranks by `I × (1 + days_overdue)`. Not the same as pack difficulty (easy→advanced).

---

## Notes structure

1. **Topic Index** table = the numbered list of present topics in that file  
2. Matching `## \`L*\` / \`MT*\` —` headings  
3. Grounded body; no quiz from meta sections  

**Math Core:** `MT1-T01` reference + `MT0-T01`…`MT0-T09` worksheet cards (basics first).

---

## Quiz engine (`topic_loop` — lectures)

Walk Topic Index order; ≥2 Q/topic; tag `topic_id` + `note_path`; topic_pack ReviewCards.

## Daily Study Loop + Math Core

Math Core (`MT1-T01`) first + 20Q; then up to 2 other unmastered tags by importance × overdue.

## Difficulty ladder (MT)

`easy` → `medium` → `hard` → `advanced` · generators at easy only · ≥80% unlocks next.

## Cursor rules

- `.cursor/rules/notes-generation.mdc`
- `.cursor/rules/quiz-generation.mdc`
- Topic list: `docs/PRESENT_TOPICS.md`
