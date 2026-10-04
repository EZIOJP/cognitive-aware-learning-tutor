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

  it("keeps plan-only agendas planned and still allows tracked actuals", () => {
    expect(calendarLayerVisibility({ planned: false, actual: true, planningOnly: true })).toEqual({
      showPlanned: true,
      showActual: true,
      loadOverlay: true,
    });
  });
});
