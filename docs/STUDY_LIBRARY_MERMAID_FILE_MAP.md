# Study Library Mermaid/Code Fix — File Map (for AI agents)

One-line purpose per file. Paths relative to repo root.

## Entry & routing

- `src/plugins/core_plugins.tsx` — Route `/lecture-notes` → `LectureNotesPage`
- `src/pages/study/LectureNotesPage.tsx` — **Main page**: LLM config, `sectionEdit` wiring, `canRegenerate` gating (BUG: hides buttons when LLM offline)

## Viewer & editor shell

- `src/components/study/StudyLibraryViewer.tsx` — Note header (Edit, Export, **Fix all blocks**), toggles read vs edit mode
- `src/components/study/MarkdownNoteEditor.tsx` — Full-note markdown editor (split/preview), selection regenerate
- `src/components/study/StudyLibraryIntelligenceHub.tsx` — LLM provider/model prefs (lmstudio URL, gemma model)

## Markdown rendering

- `src/components/study/MarkdownNote.tsx` — `react-markdown` + lazy `MermaidBlock` / `PythonCodeBlock`; assigns `blockIndex` per fence
- `src/components/study/markdownRepair.ts` — `repairNoteMarkdown()`, fence repair, step-code wrap
- `src/components/study/noteBlockUtils.ts` — `listFencedBlocks`, `replaceFencedBlock`, context extractors, `expandSelectionToFencedBlock`

## Block components (where toolbar lives)

- `src/components/study/MermaidBlock.tsx` — Renders mermaid; `useSectionBlockEdit`; applies `sanitizeMermaidSource` on render
- `src/components/study/PythonCodeBlock.tsx` — Pyodide run; block toolbar
- `src/components/study/CodeBlock.tsx` — Non-python code fences; toolbar
- `src/components/study/SectionBlockToolbar.tsx` — **UI: Edit | Fix with AI | Save** (hidden if `canRegenerate=false`)
- `src/components/study/useSectionBlockEdit.tsx` — Edit/regenerate logic; local sanitize before LLM call
- `src/components/study/useSelectionRegenerate.tsx` — Selection bar + accept/rollback in editor

## Syntax fix (no LLM)

- `src/components/study/mermaidSanitize.ts` — **Client-side mermaid fix**: edge `-->|label|`, stadium→brackets, arr[i], `&` links
- `src/components/study/pyodideRunner.ts` — Lazy Pyodide; auto `loadPackage('numpy')` on import

## API client

- `src/api/transcriptsClient.ts` — `getLlmConfig`, `regenerateNoteBlock`, `regenerateNoteSelection`, `repairAllNoteBlocks`, `saveNoteContent`

## Backend API

- `backend/transcripts/router.py` — Routes: `/llm-config`, `/library/regenerate-block`, `/library/regenerate-selection`, `/library/repair-all-blocks`
- `backend/transcripts/block_regenerate.py` — LLM prompts + `regenerate_block()` / `regenerate_selection()`
- `backend/transcripts/note_block_repair.py` — `repair_all_blocks()` batch loop
- `backend/transcripts/cleanup.py` — `sanitize_mermaid_source()`, `postprocess_markdown()` for note generation
- `backend/transcripts/notes_generator.py` — LLM note generation prompts (should include mermaid rules)
- `backend/core/ollama_client.py` — `llm_reachable()`, `ollama_generate()`; **reachable=false hides all AI buttons**
- `backend/config.py` — `ollama_enabled` default **False**

## Config

- `.env.example` — `OLLAMA_ENABLED=1`, `OLLAMA_URL`, `OLLAMA_MODEL`, `LLM_PROVIDER`

## Tests

- `tests/test_mermaid_sanitize.test.ts`
- `tests/test_note_block_utils.test.ts`
- `tests/test_note_block_repair.py`
- `tests/test_block_regenerate.py`
- `tests/test_notes_postprocess.py`

## Styles

- `src/styles/study-library.css` — Study library layout
- `src/styles/education-canvas.css` — Markdown block chrome

## Related docs

- `docs/STUDY_LIBRARY_MERMAID_HANDOFF.md` — Full problem report + repro + fix checklist
