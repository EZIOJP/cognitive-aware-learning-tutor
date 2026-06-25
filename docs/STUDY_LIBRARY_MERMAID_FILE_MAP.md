# Study Library Mermaid — File Map (for AI agents)

One-line purpose per file. **Updated 2026-06-24.**

**Full handoff:** [MERMAID_RENDER_AND_REGEN_HANDOFF.md](./MERMAID_RENDER_AND_REGEN_HANDOFF.md)  
**Code excerpts:** [MERMAID_CODE_REFERENCE.md](./MERMAID_CODE_REFERENCE.md)

---

## Entry & routing

| File | Role |
|------|------|
| `src/plugins/core_plugins.tsx` | Route `/lecture-notes` → `LectureNotesPage` |
| `src/pages/study/LectureNotesPage.tsx` | LLM picker, `handleBlockSave`, `handleBlockRegenerate`, `sectionEdit` wiring |

---

## Viewer shell

| File | Role |
|------|------|
| `src/components/study/StudyLibraryViewer.tsx` | Note header: Edit, Export, Fix syntax / Fix all blocks |
| `src/components/study/MarkdownNoteEditor.tsx` | Full-note edit + selection regenerate |
| `src/components/study/RepairPackImportDialog.tsx` | Import external repair pack JSON |

---

## Markdown rendering

| File | Role |
|------|------|
| `src/components/study/MarkdownNote.tsx` | `react-markdown`; **fenced-only** `blockIndex`; lazy `MermaidBlock` |
| `src/components/study/markdownRepair.ts` | `repairNoteMarkdown()` before save/render |
| `src/components/study/noteBlockUtils.ts` | `listFencedBlocks`, `replaceFencedBlock` (throws if bad index) |

---

## Mermaid block stack

| File | Role |
|------|------|
| `src/components/study/MermaidBlock.tsx` | Render hook, toolbar, auto-heal save |
| `src/components/study/mermaidConfig.ts` | `mermaid.initialize`, `validateMermaidSource`, `renderMermaidSvg` + aggressive retry |
| `src/components/study/mermaidSanitize.ts` | Client sanitize + `aggressiveSanitizeMermaidSource` (mirrors Python) |
| `src/components/study/SectionBlockToolbar.tsx` | Edit \| Fix syntax \| Fix with AI \| Save |
| `src/components/study/useSectionBlockEdit.tsx` | Edit/regenerate/sanitize state machine |

---

## API client

| File | Role |
|------|------|
| `src/api/transcriptsClient.ts` | `loadLlmPrefs`, `getLlmConfig`, `regenerateNoteBlock`, `saveNoteContent`, `repairAllNoteBlocks` |

---

## Backend — Mermaid strict + cleanup

| File | Role |
|------|------|
| `backend/transcripts/mermaid_strict.py` | **Source of truth:** rules, `sanitize_mermaid_source`, `aggressive_sanitize_mermaid_source`, lint |
| `backend/transcripts/cleanup.py` | Re-exports sanitizer for notes pipeline |
| `backend/transcripts/notes_generator.py` | LLM note gen; embeds rules + final sanitize |

---

## Backend — regen & repair

| File | Role |
|------|------|
| `backend/transcripts/block_regenerate.py` | `regenerate_block()`, prompts, post-LLM sanitize |
| `backend/transcripts/note_block_repair.py` | `repair_all_blocks()` batch (syntax-only or + LLM) |
| `backend/transcripts/router.py` | `/llm-config`, `/regenerate-block`, `/repair-all-blocks`, PUT file content |
| `backend/transcripts/library.py` | `save_note_content()` writes `data/notes/` |

---

## Backend — LLM client

| File | Role |
|------|------|
| `backend/core/ollama_client.py` | `llm_reachable()`, `ollama_generate()`, LM Studio `reasoning: off` |
| `backend/config.py` | `ollama_enabled` (default False — set `OLLAMA_ENABLED=1`) |

---

## Tests

| File | Covers |
|------|--------|
| `tests/test_mermaid_sanitize.test.ts` | Frontend sanitize rules |
| `tests/test_mermaid_strict.py` | Backend sanitize + aggressive + Gemma output |
| `tests/test_note_block_utils.test.ts` | `replaceFencedBlock`, context extractors |
| `tests/test_note_block_repair.py` | Batch repair |
| `tests/test_block_regenerate.py` | Regenerate LLM gate |

---

## Sample data & docs

| File | Role |
|------|------|
| `data/notes/live_captions_20260623_204143_20260624_030551.md` | Real note with broken indexing mermaid |
| `docs/STUDY_LIBRARY_MERMAID_SAMPLE_BROKEN.md` | Isolated broken diagram fixtures |
| `docs/MERMAID_RENDER_AND_REGEN_HANDOFF.md` | **Primary handoff** (render + regen + LLM) |
| `docs/MERMAID_CODE_REFERENCE.md` | Code snippets by layer |

---

## Config

| File | Role |
|------|------|
| `.env.example` | `OLLAMA_ENABLED`, `OLLAMA_URL`, `OLLAMA_MODEL`, `LLM_PROVIDER` |
