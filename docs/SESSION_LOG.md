# Session Log

Running checklist for Cursor sessions.

**Current focus:** Second-brain study loop — capture → grounded notes → corpus → quiz → spaced review.

---

## 2026-06-25 — Second brain loop

**Done:**
- [x] Full PDF ingest (CLI, API, Knowledge Base UI, auto-setup)
- [x] Grounded notes button on Lecture Notes (`CORPUS_GROUNDED_NOTES=1`)
- [x] Studio Done → auto-ingest transcript + note into corpus
- [x] Web generate → corpus handoff after save
- [x] `build-golden` CLI + expected chunk counts in `CORPUS_STATUS.md`
- [x] Markdown code-block extraction + repair pipeline fixes

**Verify:**
- [ ] `CORPUS_GROUNDED_NOTES=1` in `.env`, restart backend
- [ ] Knowledge Base → Build (or status shows ~3500+ chunks)
- [ ] Studio Generate → Done dialog mentions corpus chunks
- [ ] Lecture Notes → Generate grounded (RAG) on a transcript
- [ ] `python -m pytest tests/test_corpus.py -m integration`

---

## Phase 1 — GRE Vocabulary ✅

See [GRE_VOCAB_PHASE1.md](GRE_VOCAB_PHASE1.md). ROADMAP marks Phase 1 complete.

---

## Session template

```markdown
## YYYY-MM-DD

**Today's task:** [one item]

**Done:**
-

**Blocked / notes:**
-
```
