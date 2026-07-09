/**
 * Study note renderer — single import surface for markdown notes in the webapp.
 * Re-exports the rebuilt viewer/editor with debounced lite preview.
 */

export {
  MarkdownNote as NoteDocumentView,
  type MarkdownNoteSectionProps as NoteSectionEditProps,
  type NotePreviewMode,
} from "../../components/study/MarkdownNote";

export { MarkdownNoteEditor as NoteDocumentEditor } from "../../components/study/MarkdownNoteEditor";

export {
  prepareNoteMarkdown,
  finalizeNoteMarkdown,
  applyBlockUpdate,
  listFencedBlocks,
} from "../study-notes";
