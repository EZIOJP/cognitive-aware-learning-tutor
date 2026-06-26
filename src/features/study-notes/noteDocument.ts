/**
 * Canonical note-document model — mirrors backend/transcripts/note_document.py
 */
import { layoutSafeMermaidSource } from "../mermaid/pipeline";
import {
  repairAllFences,
  repairMermaidFences,
  repairNoteMarkdown,
  repairSplitCodeFences,
  repairStepCodeBlocks,
} from "../../components/study/markdownRepair";

export type FencedBlock = {
  index: number;
  lang: string;
  content: string;
  start: number;
  end: number;
};

const FENCE_BLOCK_RE = /```(\w*)[^\S\r\n]*\r?\n([\s\S]*?)```/g;
const MERMAID_RE = /```mermaid\s*\n([\s\S]*?)```/gi;

export { repairNoteMarkdown };

export function prepareNoteMarkdown(raw: string): string {
  return repairNoteMarkdown(raw);
}

export function listFencedBlocks(markdown: string): FencedBlock[] {
  const blocks: FencedBlock[] = [];
  let match: RegExpExecArray | null;
  const re = new RegExp(FENCE_BLOCK_RE.source, "g");
  while ((match = re.exec(markdown)) !== null) {
    blocks.push({
      index: blocks.length,
      lang: (match[1] || "text").toLowerCase(),
      content: match[2].replace(/\n$/, ""),
      start: match.index,
      end: match.index + match[0].length,
    });
  }
  return blocks;
}

function formatFence(lang: string, body: string): string {
  const l = lang.trim();
  if (l && l !== "text") {
    return `\`\`\`${l}\n${body.trim()}\n\`\`\``;
  }
  return `\`\`\`\n${body.trim()}\n\`\`\``;
}

export function replaceFencedBlock(markdown: string, blockIndex: number, newContent: string): string {
  const blocks = listFencedBlocks(markdown);
  const block = blocks[blockIndex];
  if (!block) {
    throw new Error(
      `Could not save block ${blockIndex}: note has ${blocks.length} fenced block${blocks.length === 1 ? "" : "s"}. Hard-refresh the page (Ctrl+Shift+R) and try again.`,
    );
  }
  return markdown.slice(0, block.start) + formatFence(block.lang, newContent) + markdown.slice(block.end);
}

export function applyMermaidLayoutSafe(body: string): string {
  return layoutSafeMermaidSource(body);
}

export function applyBlockUpdate(
  markdown: string,
  blockIndex: number,
  newContent: string,
  opts?: { lang?: string },
): string {
  const blocks = listFencedBlocks(markdown);
  const block = blocks[blockIndex];
  if (!block) {
    throw new Error(`Block index ${blockIndex} out of range`);
  }
  const lang = opts?.lang ?? block.lang;
  const body = lang === "mermaid" ? applyMermaidLayoutSafe(newContent) : newContent;
  return replaceFencedBlock(markdown, blockIndex, body);
}

export function finalizeNoteMarkdown(md: string): string {
  const prepared = prepareNoteMarkdown(md);
  return prepared.replace(MERMAID_RE, (_match, inner: string) => {
    const body = applyMermaidLayoutSafe(inner);
    return `\`\`\`mermaid\n${body}\n\`\`\``;
  });
}

export { layoutSafeMermaidSource } from "../mermaid/pipeline";

// Re-export repair steps for tests / direct use
export { repairSplitCodeFences, repairAllFences, repairStepCodeBlocks, repairMermaidFences };
