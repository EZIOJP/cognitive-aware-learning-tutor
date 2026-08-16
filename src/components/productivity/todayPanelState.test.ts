import { describe, expect, it } from "vitest";
import { shouldShowDetailedBlockForm } from "./TodayPanel";

describe("shouldShowDetailedBlockForm", () => {
  it("keeps the detailed block form hidden until requested", () => {
    expect(shouldShowDetailedBlockForm(false, false)).toBe(false);
  });

  it("opens for Add block and for a calendar slot", () => {
    expect(shouldShowDetailedBlockForm(true, false)).toBe(true);
    expect(shouldShowDetailedBlockForm(false, true)).toBe(true);
  });
});
