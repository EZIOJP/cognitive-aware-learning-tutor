# Session Log

Running checklist for Cursor sessions. Check items off here and in [ROADMAP.md](ROADMAP.md) when done.

**Phase 1 focus:** GRE Vocabulary MVP — Read → Quiz → Report → Low-Mastery loop.

---

## 2026-06-02

### Setup & kernel
- [x] Cursor rules in `.cursor/rules/*.mdc`
- [x] File kernel: `AGENTS.md`, `docs/FILE_MAP.md`, `docs/SESSION_LOG.md`
- [x] Repo layout tracker: `docs/PROJECT_LAYOUT.md`, `docs/README.md`
- [x] Root cleanup: `run.bat` only at root; `scripts/`, `backend/`, `data/`, `assets/`

### Audits (do before large refactors)
- [ ] Audit Read Mode route (`/gre-vocab/read`, filtered modes)
- [ ] Audit low-mastery route (`/gre-vocab/read/low-mastery`)
- [ ] Audit due review route (`/gre-vocab/read/due`)
- [ ] Audit Cycle Manager dashboard (`/gre-vocab/cycle`)
- [ ] Audit read → quiz → report flow in `CycleManager.tsx`
- [ ] Audit low-mastery loop (prompt → re-read → re-quiz)

### Fixes & polish
- [ ] Fix progress persistence gaps (localStorage vs API)
- [ ] Admin: reset / export / import workflows
- [ ] Empty, loading, and error states across vocab pages
- [ ] Run production build (`npm run build`)

---

## Session template

Copy into a new dated section when you start work:

```markdown
## YYYY-MM-DD

**Today’s task:** [one item from above]

**Done:**
- 

**Blocked / notes:**
- 
```

## Quick start prompt

```
@AGENTS.md @docs/PROJECT_LAYOUT.md @docs/FILE_MAP.md @docs/SESSION_LOG.md

Today's task: [paste one unchecked item]
```
