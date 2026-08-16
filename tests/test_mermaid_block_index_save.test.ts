import { describe, expect, it } from "vitest";
import {
  applyBlockUpdate,
  listFencedBlocks,
  resolveFencedBlockIndex,
} from "../src/features/study-notes/noteDocument";

describe("resolveFencedBlockIndex / applyBlockUpdate", () => {
  const md = `# Note

\`\`\`python
print(1)
\`\`\`

Some indented:

    not_a_fence = True

\`\`\`mermaid
flowchart TD
  A-->B
\`\`\`
`;

  it("lists only real fences (not indented code)", () => {
    const blocks = listFencedBlocks(md);
    expect(blocks).toHaveLength(2);
    expect(blocks[0].lang).toBe("python");
    expect(blocks[1].lang).toBe("mermaid");
  });

  it("resolves mermaid by previous content when hint index is inflated", () => {
    const idx = resolveFencedBlockIndex(md, {
      hintIndex: 209,
      lang: "mermaid",
      content: "flowchart TD\n  A-->B",
    });
    expect(idx).toBe(1);
  });

  it("saves mermaid fix despite wrong UI index", () => {
    const updated = applyBlockUpdate(md, 209, "flowchart TD\n  A-->C", {
      lang: "mermaid",
      previousContent: "flowchart TD\n  A-->B",
    });
    expect(updated).toContain("A-->C");
    expect(updated).not.toContain("A-->B");
    expect(listFencedBlocks(updated)).toHaveLength(2);
  });
});
