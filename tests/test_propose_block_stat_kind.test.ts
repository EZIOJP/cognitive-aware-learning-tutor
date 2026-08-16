import { describe, expect, it } from "vitest";
import { proposeBlockStatKind } from "../src/components/productivity/proposeBlockStats";

describe("proposeBlockStatKind (Build status when plan already present)", () => {
  it("counts saved study blocks by category, not only source=study", () => {
    expect(
      proposeBlockStatKind({
        source: "existing",
        category: "study",
        title: "Scaler — daily lessons",
      }),
    ).toBe("study");
  });

  it("classifies meals/bath as routine-like and breaks by title", () => {
    expect(
      proposeBlockStatKind({ source: "existing", category: "personal", title: "Bath / self-care" }),
    ).toBe("routine");
    expect(
      proposeBlockStatKind({ source: "existing", category: "food", title: "Breakfast" }),
    ).toBe("routine");
    expect(proposeBlockStatKind({ source: "existing", category: "break", title: "Break" })).toBe(
      "break",
    );
  });

  it("keeps explicit draft sources", () => {
    expect(proposeBlockStatKind({ source: "study", category: "personal" })).toBe("study");
    expect(proposeBlockStatKind({ source: "break", category: "study" })).toBe("break");
    expect(proposeBlockStatKind({ source: "routine", category: "study" })).toBe("routine");
  });
});
