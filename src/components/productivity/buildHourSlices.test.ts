import { describe, expect, it } from "vitest";
import { buildHourSlicesFromSessions } from "./buildHourSlices";
import type { ActualSession } from "../../api/plannerClient";

describe("buildHourSlicesFromSessions", () => {
  it("builds hour chips from overlay sessions when native hour_slices are empty", () => {
    const day = new Date(2026, 8, 14); // local Sep 14
    const sessions: ActualSession[] = [
      {
        session_id: "a",
        start_time: "2026-09-13T18:45:00Z", // 00:15 IST
        end_time: "2026-09-13T19:05:00Z", // 00:35 IST
        source: "desktop_tracker",
        category: "Work",
        app_name: "cursor.exe",
        window_title: "x",
        task_id: null,
      },
    ];
    const slices = buildHourSlicesFromSessions(sessions, day);
    expect(slices.length).toBeGreaterThan(0);
    expect(slices.some((s) => s.hour === 0 && s.segments.some((g) => g.app_or_label === "cursor"))).toBe(
      true,
    );
  });
});
