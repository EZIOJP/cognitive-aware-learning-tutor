export type FencedBlock = {
  index: number;
  lang: string;
  content: string;
  start: number;
  end: number;
};

const FENCE_BLOCK_RE = /```(\w*)[^\S\r\n]*\r?\n([\s\S]*?)```/g;

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

export function replaceFencedBlock(markdown: string, blockIndex: number, newContent: string): string {
  const blocks = listFencedBlocks(markdown);
  const block = blocks[blockIndex];
  if (!block) return markdown;
  const lang = block.lang && block.lang !== "text" ? block.lang : "";
  const fence = lang
    ? `\`\`\`${lang}\n${newContent.trim()}\n\`\`\``
    : `\`\`\`\n${newContent.trim()}\n\`\`\``;
  return markdown.slice(0, block.start) + fence + markdown.slice(block.end);
}

export function extractMarkdownCode(children: unknown): string {
  if (children == null) return "";
  if (Array.isArray(children)) {
    return children
      .map((child) => {
        if (typeof child === "string") return child;
        if (child == null) return "";
        return String(child);
      })
      .join("")
      .replace(/\n$/, "");
  }
  return String(children).replace(/\n$/, "");
}

export function isBrokenBlockContent(content: string): boolean {
  const t = content.trim().toLowerCase();
  return !t || t === "undefined" || t === "null" || t === "[object object]";
}

const FENCE_PLACEHOLDER_RE = /```[\w]*[^\S\r\n]*\r?\n[\s\S]*?```/g;

function stripFencedBlocksForContext(text: string): string {
  return text.replace(FENCE_PLACEHOLDER_RE, () => "[code or diagram block omitted]\n").trim();
}

/**
 * Markdown above/below a fenced block for LLM regenerate (excludes other fenced blocks).
 */
export function extractBlockSurroundingContext(
  markdown: string,
  blockIndex: number,
  opts?: { linesBefore?: number; linesAfter?: number; maxChars?: number; blockContent?: string },
): string {
  const linesBefore = opts?.linesBefore ?? 45;
  const linesAfter = opts?.linesAfter ?? 30;
  const maxChars = opts?.maxChars ?? 3500;

  const blocks = listFencedBlocks(markdown);
  const block = blocks[blockIndex];
  if (!block) return markdown.slice(0, maxChars);

  const blockBody = opts?.blockContent ?? block.content;

  const beforeRaw = markdown.slice(0, block.start).split("\n").slice(-linesBefore).join("\n");
  const afterRaw = markdown.slice(block.end).split("\n").slice(0, linesAfter).join("\n");

  const before = stripFencedBlocksForContext(beforeRaw);
  const after = stripFencedBlocksForContext(afterRaw);

  const parts = [
    before && `--- Context above this block ---\n${before}`,
    `--- Block to fix/regenerate ---\n\`\`\`${block.lang}\n${blockBody}\n\`\`\``,
    after && `--- Context below this block ---\n${after}`,
  ].filter(Boolean);

  return parts.join("\n\n").slice(0, maxChars);
}

/**
 * Markdown above/below a character range (for selection regenerate).
 */
export function extractSelectionSurroundingContext(
  markdown: string,
  start: number,
  end: number,
  opts?: { linesBefore?: number; linesAfter?: number; maxChars?: number },
): string {
  const linesBefore = opts?.linesBefore ?? 40;
  const linesAfter = opts?.linesAfter ?? 25;
  const maxChars = opts?.maxChars ?? 4000;

  const beforeRaw = markdown.slice(0, Math.max(0, start)).split("\n").slice(-linesBefore).join("\n");
  const afterRaw = markdown.slice(Math.min(end, markdown.length)).split("\n").slice(0, linesAfter).join("\n");
  const selection = markdown.slice(start, end);

  const before = stripFencedBlocksForContext(beforeRaw);
  const after = stripFencedBlocksForContext(afterRaw);

  const parts = [
    before && `--- Context above selection ---\n${before}`,
    `--- Selected fragment ---\n${selection}`,
    after && `--- Context below selection ---\n${after}`,
  ].filter(Boolean);

  return parts.join("\n\n").slice(0, maxChars);
}

const CODE_FENCE_LANGS = new Set(["python", "py", "javascript", "js", "typescript", "ts"]);

export type ExpandedSelection = {
  start: number;
  end: number;
  text: string;
  lang: string | null;
  expanded: boolean;
};

/** If selection touches a mermaid/python fence, expand to the full fenced block for fixing. */
export function expandSelectionToFencedBlock(
  markdown: string,
  start: number,
  end: number,
): ExpandedSelection {
  const blocks = listFencedBlocks(markdown);
  for (const block of blocks) {
    const fixable = block.lang === "mermaid" || CODE_FENCE_LANGS.has(block.lang);
    if (!fixable) continue;
    if (start < block.end && end > block.start) {
      return {
        start: block.start,
        end: block.end,
        text: markdown.slice(block.start, block.end),
        lang: block.lang,
        expanded: start !== block.start || end !== block.end,
      };
    }
  }
  return {
    start,
    end,
    text: markdown.slice(start, end),
    lang: null,
    expanded: false,
  };
}

export function inferSelectionFixKind(text: string): "mermaid" | "code" | "markdown" {
  const trimmed = text.trim();
  const fence = /^```(mermaid|python|py|javascript|js)\s*\n/i.exec(trimmed);
  if (fence) {
    return fence[1].toLowerCase() === "mermaid" ? "mermaid" : "code";
  }
  if (/^(graph|flowchart)\s/im.test(trimmed)) return "mermaid";
  if (/^\s*(import |from |def |class |print\(|W\s*=)/m.test(trimmed)) return "code";
  return "markdown";
}
