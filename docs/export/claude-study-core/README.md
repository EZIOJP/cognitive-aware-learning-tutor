# Claude Study Core — Knowledge Pack

**Export date:** 2026-09-03  
**Product:** Cognitive-Aware Learning Tutor (CALT) — study notes / quiz / FSRS core only.

**Out of scope for this pack:** productivity desktop tracker, distraction gate/blocking, wearables, bible ritual, planner hard-block.

---

## Recommended upload (Claude Project)

Attach **exactly these four** (order matters for Claude’s first read):

1. `00-CLAUDE-PROJECT-INSTRUCTIONS.md` — paste into **Project custom instructions**, *or* attach and say “follow this as system rules”
2. `01-COMPLETE-OVERVIEW.md` — architecture + EdTech strategy mapping
3. `02-NOTES-QUESTIONS-AND-SCHEMAS.md` — worked note↔question example
4. `03-STUDY-LOOP-PLAN-FOR-CLAUDE.md` — implementable 9-task plan

**Optional 5th:** `appendix-edtech-strategy.md` (full cleaned EdTech RTF). Files A–D are sufficient alone; use the appendix only if you want the long pedagogy/FSRS/DKT prose in context.

Do **not** attach productivity / gate / wearables docs.

---

## Project vs chat

| Mode | Tip |
|------|-----|
| **Claude Project** | Unlimited Project Knowledge files (≤30MB each). Context window is still the real limit — prefer these 3–4 dense files over dumping the whole repo. Put `00` in custom instructions. |
| **Chat upload** | Claude chat typically allows ≤20 files per conversation. Attach the same 00→03 set; do not flood with unrelated markdown. |

**Anthropic practicality:** more files ≠ better answers. A few dense, cross-linked docs beat a folder dump. If a reply feels “forgetful,” re-@ mention `01` + `03` rather than uploading more.

---

## How to start a Claude session

1. Load Project instructions (`00`).  
2. Attach `01`, `02`, `03`.  
3. First user message example:

```text
Implement Study Loop Task 1 (read-card digester) against this repo.
Status: planned, not implemented. Follow ADR-001 locks in 00.
TDD: write failing pytest first. Do not touch productivity/gate code.
```

---

## Sibling export (unchanged)

Google Deep Research / Gemini pack remains at:

`docs/export/study-core/`

(`01-ARCHITECTURE…`, `02-NOTES…`, `03-DEEP-RESEARCH-PROMPT.md`, README). This Claude pack refines that content for Anthropic Project/chat; it does not replace the Deep Research prompt file.
