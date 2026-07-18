# Quiz draft quality loop — design (2026-07-17)

## Locked choices
- User sets **question count** (5–25, or 20–50 for cover_all) + **focus** (`mixed` | `concept` | `coding` | `cover_all`).
- Call plan is **automatic** (role-based batches of ≤6), not a raw call slider.
- **cover_all**: multi-call over note sections + concept/coding/connect; **auto-saves** quiz markdown to the library folder.
- **Generate** only fills an editable draft; **Take quiz** is separate.
- Each item carries `concept` (+ hint). Wrong → show topic/hint; requeue in session + SRS deck.

## Out of scope here
- Corpus RAG for quiz (stays off).
- Editing raw LLM call count manually (cover_all chooses the plan).
