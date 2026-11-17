import { describe, expect, it } from "vitest";
import { calendarLayerVisibility } from "./PlannerCalendar";

describe("calendarLayerVisibility", () => {
  it("hides planned blocks independently of tracked actuals", () => {
    expect(calendarLayerVisibility({ planned: false, actual: true, planningOnly: false })).toEqual({
      showPlanned: false,
      showActual: true,
      loadOverlay: true,
    });
  });

  it("respects P/A toggles on plan schedule preview too", () => {
    expect(calendarLayerVisibility({ planned: false, actual: true, planningOnly: true })).toEqual({
      showPlanned: false,
      showActual: true,
      loadOverlay: true,
    });
  });
});
