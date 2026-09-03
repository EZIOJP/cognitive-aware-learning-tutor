import { describe, expect, it } from "vitest";
import {
  exportVisibleMonthBounds,
  isExportDayMuted,
} from "./ExportRangeCalendar";

describe("ExportRangeCalendar helpers", () => {
  it("exportVisibleMonthBounds includes week fringe around the month", () => {
    const { start, end } = exportVisibleMonthBounds(new Date(2026, 6, 15)); // July 2026
    expect(start <= "2026-07-01").toBe(true);
    expect(end >= "2026-07-31").toBe(true);
  });

  it("isExportDayMuted fades empty past days but not future", () => {
    const presence = new Set(["2026-07-10"]);
    expect(isExportDayMuted("2026-07-10", presence, "2026-07-12")).toBe(false);
    expect(isExportDayMuted("2026-07-11", presence, "2026-07-12")).toBe(true);
    expect(isExportDayMuted("2026-07-13", presence, "2026-07-12")).toBe(false);
  });
});
