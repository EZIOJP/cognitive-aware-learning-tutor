/**
 * Canonical note-document model — mirrors backend/transcripts/note_document.py
 */
import {
  repairAllFences,
  repairMermaidFences,
  repairNoteMarkdown,
  repairSplitCodeFences,
  repairStepCodeBlocks,
} from "../../components/study/markdownRepair";
import { sanitizeMermaidSource } from "../mermaid/pipeline";

export type FencedBlock = {
  index: number;
  lang: string;
  content: string;
  start: number;
  end: number;
};

const FENCE_BLOCK_RE = /```(\w*)[^\S\r\n]*\r?\n([\s\S]*?)```/g;

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

/** Normalize fence body for index/content matching (renderer vs regex). */
export function normalizeFenceBody(s: string): string {
  return String(s ?? "")
    .replace(/\r\n/g, "\n")
    .replace(/\n$/, "")
    .trimEnd();
}

function langsCompatible(a: string, b: string): boolean {
  const x = (a || "text").toLowerCase();
  const y = (b || "text").toLowerCase();
  if (x === y) return true;
  if ((x === "python" || x === "py") && (y === "python" || y === "py")) return true;
  if ((x === "javascript" || x === "js") && (y === "javascript" || y === "js")) return true;
  if ((x === "typescript" || x === "ts") && (y === "typescript" || y === "ts")) return true;
  if ((x === "text" || x === "") && (y === "text" || y === "")) return true;
  return false;
}

/**
 * Resolve a fenced block index for save/regenerate.
 * Prefer hintIndex when it still matches; otherwise match by body (+ optional lang).
 */
export function resolveFencedBlockIndex(
  markdown: string,
  opts: { hintIndex?: number; lang?: string; content?: string },
): number {
  const blocks = listFencedBlocks(markdown);
  const want = opts.content != null ? normalizeFenceBody(opts.content) : "";
  const lang = (opts.lang || "").toLowerCase();

  if (opts.hintIndex != null && blocks[opts.hintIndex]) {
    const b = blocks[opts.hintIndex];
    if (!want || normalizeFenceBody(b.content) === want) {
      if (!lang || langsCompatible(b.lang, lang)) return opts.hintIndex;
    }
  }

  if (want) {
    const exact = blocks.findIndex(
      (b) =>
        normalizeFenceBody(b.content) === want && (!lang || langsCompatible(b.lang, lang)),
    );
    if (exact >= 0) return exact;
    // Lang-only unique match when body already changed (AI fix) but hint was wrong
    if (lang) {
      const sameLang = blocks.filter((b) => langsCompatible(b.lang, lang));
      if (sameLang.length === 1) return sameLang[0].index;
    }
  }

  return -1;
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

/** Trim + strip fence wrappers only — do not rewrite Mermaid syntax. */
export function applyMermaidLayoutSafe(body: string): string {
  return sanitizeMermaidSource(body);
}

export function applyBlockUpdate(
  markdown: string,
  blockIndex: number,
  newContent: string,
  opts?: { lang?: string; previousContent?: string },
): string {
  const resolved = resolveFencedBlockIndex(markdown, {
    hintIndex: blockIndex,
    lang: opts?.lang,
    content: opts?.previousContent,
  });
  if (resolved < 0) {
    const n = listFencedBlocks(markdown).length;
    throw new Error(
      `Block index ${blockIndex} out of range (note has ${n} fenced block${n === 1 ? "" : "s"}). Hard-refresh (Ctrl+Shift+R) and try again.`,
    );
  }
  const blocks = listFencedBlocks(markdown);
  const block = blocks[resolved];
  const body = (opts?.lang ?? block.lang) === "mermaid" ? newContent.trim() : newContent;
  return replaceFencedBlock(markdown, resolved, body);
}

export function finalizeNoteMarkdown(md: string): string {
  // Fence repair only — leave ```mermaid bodies untouched for Mermaid.js.
  return prepareNoteMarkdown(md);
}

export { layoutSafeMermaidSource, sanitizeMermaidSource } from "../mermaid/pipeline";

// Re-export repair steps for tests / direct use
export { repairSplitCodeFences, repairAllFences, repairStepCodeBlocks, repairMermaidFences };
