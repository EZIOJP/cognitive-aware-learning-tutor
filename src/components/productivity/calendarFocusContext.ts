import { createContext, useContext } from "react";

export type CalendarFocusContextValue = {
  focusedId: number | null;
};

export const CalendarFocusContext = createContext<CalendarFocusContextValue>({
  focusedId: null,
});

export function useCalendarFocus() {
  return useContext(CalendarFocusContext);
}
