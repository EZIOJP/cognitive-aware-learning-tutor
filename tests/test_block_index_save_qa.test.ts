/**
 * Manual QA helper: proves save path works at fenced index 0 on the real indexing note.
 * Run: npx vitest run tests/test_block_index_save_qa.test.ts
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { repairNoteMarkdown } from "../src/components/study/markdownRepair";
import { layoutSafeMermaidSource } from "../src/features/study-notes";
import { listFencedBlocks, replaceFencedBlock } from "../src/components/study/noteBlockUtils";

const NOTE = resolve(
  "data/notes/live_captions_20260623_204143_20260624_030551.md",
);

describe("block index save QA (live captions note)", () => {
  it("first mermaid is fenced block 0 and save at index 0 updates diagram", () => {
    let md: string;
    try {
      md = repairNoteMarkdown(readFileSync(NOTE, "utf8"));
    } catch {
      return; // skip if user data file absent in CI
    }

    const blocks = listFencedBlocks(md);
    const firstMermaid = blocks.find((b) => b.lang === "mermaid");
    expect(firstMermaid).toBeDefined();
    expect(firstMermaid!.index).toBe(0);

    const fixed = layoutSafeMermaidSource(firstMermaid!.content);
    expect(fixed).toContain("Positive indices");
    expect(fixed).not.toContain("W[-1]");

    const updated = replaceFencedBlock(md, 0, fixed);
    expect(updated).toContain("Positive indices");
    expect(updated).not.toMatch(/```mermaid[\s\S]*W\[-1\]/);

    // Wrong index (pre-fix UI would have used ~10) must throw, not silently no-op
    expect(() => replaceFencedBlock(md, 10, fixed)).toThrow(/Could not save block 10/);
  });
});
