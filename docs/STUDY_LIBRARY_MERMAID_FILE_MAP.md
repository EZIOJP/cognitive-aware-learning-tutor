# Study Library Mermaid — File Map (for AI agents)

One-line purpose per file. **Updated 2026-06-24.**

**Full handoff:** [MERMAID_RENDER_AND_REGEN_HANDOFF.md](./MERMAID_RENDER_AND_REGEN_HANDOFF.md)

---

## Entry & routing

| File | Role |
|------|------|
| `src/plugins/core_plugins.tsx` | Route `/lecture-notes` → `LectureNotesPage` |
| `src/pages/study/LectureNotesPage.tsx` | `persistNote`, `handleBlockSave`, `repairAndSaveNote`, `sectionEdit` |

---

## Canonical note document

| File | Role |
|------|------|
| `src/features/study-notes/noteDocument.ts` | `prepareNoteMarkdown`, `listFencedBlocks`, `replaceFencedBlock`, `finalizeNoteMarkdown` |
| `backend/transcripts/note_document.py` | Python mirror of fence + finalize pipeline |

---

## Viewer shell

| File | Role |
|------|------|
| `src/components/study/StudyLibraryViewer.tsx` | Header: Edit, Export, Fix syntax / Fix all (AI) |
| `src/components/study/MarkdownNoteEditor.tsx` | Full-note edit + selection regenerate |

---

## Markdown rendering

| File | Role |
|------|------|
| `src/components/study/MarkdownNote.tsx` | Pre-indexed fenced blocks from `prepareNoteMarkdown` |
| `src/components/study/markdownRepair.ts` | Fence repair steps (used by `noteDocument`) |
| `src/components/study/noteBlockUtils.ts` | Re-exports fence utils; context extraction for LLM |

---

## Mermaid stack

| File | Role |
|------|------|
| `src/features/mermaid/pipeline.ts` | `sanitizeMermaidSource`, `layoutSafeMermaidSource` (mirrors Python) |
| `src/features/mermaid/render.ts` | Mermaid.js init, parse, render + aggressive retry |
| `src/features/mermaid/MermaidBlockView.tsx` | Pure render UI (no auto-heal) |
| `src/components/study/MermaidBlockShell.tsx` | Toolbar + `useSectionBlockEdit` wrapper |
| `src/components/study/useSectionBlockEdit.tsx` | Fix syntax / Fix with AI / Save state machine |

---

## API client

| File | Role |
|------|------|
| `src/api/transcriptsClient.ts` | `getNoteContent` (library path), `repairAndSaveNote`, `regenerateNoteBlock`, `saveNoteContent` |

---

## Backend

| File | Role |
|------|------|
| `backend/transcripts/mermaid/pipeline.py` | Canonical sanitize + `layout_safe_mermaid_source` |
| `backend/transcripts/mermaid/regenerate.py` | LLM mermaid regen |
| `backend/transcripts/block_regenerate.py` | Single-block + selection regen |
| `backend/transcripts/note_block_repair.py` | Batch repair (uses `note_document`) |
| `backend/transcripts/notes_generator.py` | `finalize_note_markdown` before disk write |
| `backend/transcripts/router.py` | `GET/PUT library/files/.../content`, `POST .../repair-all-blocks` |

---

## Tests

| File | Role |
|------|------|
| `tests/fixtures/mermaid_cases.json` | Shared Python + TS contract fixtures |
| `tests/test_mermaid_contract.py` / `.test.ts` | Cross-stack mermaid parity |
| `tests/test_note_document.py` | Fence index + finalize |
| `tests/test_block_index_save_qa.test.ts` | Block 0 save QA on live note |
