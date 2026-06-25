import { describe, expect, it } from "vitest";
import { repairAllFences, repairNoteMarkdown, repairStepCodeBlocks } from "../src/components/study/markdownRepair";
import { extractMarkdownCode, extractBlockSurroundingContext, expandSelectionToFencedBlock, extractSelectionSurroundingContext, isBrokenBlockContent, listFencedBlocks, replaceFencedBlock } from "../src/components/study/noteBlockUtils";

describe("noteBlockUtils", () => {
  it("detects broken block content", () => {
    expect(isBrokenBlockContent("undefined")).toBe(true);
    expect(isBrokenBlockContent("import numpy as np")).toBe(false);
  });

  it("extracts markdown code from react children", () => {
    expect(extractMarkdownCode(["import numpy as np\n"])).toBe("import numpy as np");
    expect(extractMarkdownCode(undefined)).toBe("");
  });

  it("replaces fenced block by index", () => {
    const md = "# Title\n\n```python\nundefined\n```\n";
    const updated = replaceFencedBlock(md, 0, "import numpy as np\nprint(1)");
    expect(updated).toContain("import numpy as np");
    expect(updated).not.toContain("undefined");
  });

  it("throws when block index is out of range", () => {
    const md = "```mermaid\ngraph TD\nA --> B\n```";
    expect(() => replaceFencedBlock(md, 3, "graph TD\nA --> B")).toThrow(/Could not save block 3/);
  });

  it("saves first mermaid at index 0 even when many inline backticks precede it", () => {
    const inlineSpans = Array.from({ length: 10 }, (_, i) => `- use \`code_${i}\` here`).join("\n");
    const md = `${inlineSpans}

\`\`\`mermaid
flowchart TD
A[Broken] --> B[Old]
\`\`\`
`;
    expect(listFencedBlocks(md)).toHaveLength(1);
    expect(() => replaceFencedBlock(md, 10, "graph TD\nA --> B")).toThrow(/Could not save block 10/);
    const updated = replaceFencedBlock(md, 0, "flowchart TD\nA[Start] --> B{Direction}");
    expect(updated).toContain("A[Start] --> B{Direction}");
    expect(updated).not.toContain("A[Broken]");
  });
});

describe("extractBlockSurroundingContext", () => {
  it("extracts context above and below a block without other fenced blocks", () => {
    const md = `## Indexing

- Single index gets one value

\`\`\`mermaid
graph TD
A --> B
\`\`\`

- Slicing gets a subset

\`\`\`python
print(1)
\`\`\`
`;
    const ctx = extractBlockSurroundingContext(md, 0);
    expect(ctx).toContain("Context above");
    expect(ctx).toContain("Indexing");
    expect(ctx).toContain("Block to fix");
    expect(ctx).toContain("Context below");
    expect(ctx).toContain("Slicing");
    expect(ctx).not.toContain("print(1)");
  });
});

describe("expandSelectionToFencedBlock", () => {
  it("expands partial selection inside a mermaid fence", () => {
    const md = "## Topic\n\n```mermaid\ngraph TD\nA --> B\n```\n\nMore text.";
    const inner = md.indexOf("graph TD");
    const expanded = expandSelectionToFencedBlock(md, inner, inner + 8);
    expect(expanded.expanded).toBe(true);
    expect(expanded.lang).toBe("mermaid");
    expect(expanded.text).toContain("```mermaid");
    expect(expanded.text).toContain("graph TD");
  });
});

describe("extractSelectionSurroundingContext", () => {
  it("includes text above and below a character range", () => {
    const md = "## Title\n\nParagraph one.\n\nBroken mermaid here.\n\nParagraph two.";
    const start = md.indexOf("Broken");
    const end = start + "Broken mermaid here.".length;
    const ctx = extractSelectionSurroundingContext(md, start, end);
    expect(ctx).toContain("Context above");
    expect(ctx).toContain("Paragraph one");
    expect(ctx).toContain("Broken mermaid here.");
    expect(ctx).toContain("Paragraph two");
  });
});

describe("repairAllFences", () => {
  it("closes unclosed python fence before markdown heading", () => {
    const raw = "```python\nimport numpy as np\nprint(1)\n## NumPy Arrays\n\n* bullet";
    const fixed = repairAllFences(raw);
    expect(fixed).toContain("print(1)\n```\n## NumPy Arrays");
    const blocks = listFencedBlocks(fixed);
    expect(blocks.length).toBe(1);
    expect(blocks[0].lang).toBe("python");
  });
});

describe("repairNoteMarkdown", () => {
  it("repairs split fences and unclosed code before headings", () => {
    const raw = "```python\n```\nimport numpy as np\n## Title\n";
    const fixed = repairNoteMarkdown(raw);
    expect(fixed).toContain("```python");
    expect(fixed).toContain("## Title");
  });
});

describe("repairStepCodeBlocks", () => {
  it("wraps step code lines in python fences", () => {
    const raw = `Step 1: Import the library
import numpy as np

Step 2: Define a simple array
W = np.array([1, 2, 3])

print(W)`;
    const fixed = repairStepCodeBlocks(raw);
    expect(fixed).toContain("```python");
    expect(fixed).toContain("import numpy as np");
    expect(fixed).toContain("print(W)");
    const blocks = listFencedBlocks(fixed);
    expect(blocks.length).toBeGreaterThanOrEqual(2);
  });
});
