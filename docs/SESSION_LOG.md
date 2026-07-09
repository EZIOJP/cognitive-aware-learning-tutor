# Session Log

Running checklist for Cursor sessions.

**Current focus:** Close the study loop — see [docs/TASK_COMPLETION.md](docs/TASK_COMPLETION.md) Lane A.

---

## 2026-07-07 — Blank screen fix (post read-time scores)

**Done:** `serialize_session` alias; regression tests for `/api/behavior/stats` CSV path + `/api/planner/overlay/actual`; `AppErrorBoundary` (reload UI instead of white screen on HMR crashes). **Recovery:** full restart `run.bat` + browser Ctrl+Shift+R after migration `0023`.

---

## 2026-07-07 — Productivity score read-time + effective focus

**Done:** `category_scores` table + `tracked_sessions_scored` view; scores derived from category at read time (dropped `tracked_sessions.productivity_score`). `PRODUCTIVE_THRESHOLD` raised **50 → 60** for `productive_minutes` and new `effective_focus_minutes` adherence KPI.

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

## 2026-07-03 — Plan vs Actual dashboard

Plan vs Actual dashboard on Productivity calendar tab — consumes `/api/planner/blocks`, `/overlay/actual`, `/adherence`, `/api/behavior/desktop-timeline`, `/tracker-health`.

## 2026-07-07 — Activity detail UX

Calendar tab layout (Today strip + full-width planner); day sync calendar↔ribbon; shared ActivityDetailPanel with click drill-down on Day ribbon and calendar stacks.

## 2026-07-07 — Read-time productivity scores

`category_scores` table + `tracked_sessions_scored` view; scores derived at read time from category. `productive_minutes` threshold raised 50→60 (matches `PRODUCTIVE_THRESHOLD`); added `effective_focus_minutes` adherence KPI.
