import {
  differenceInCalendarDays,
  endOfWeek,
  format,
  isSameMonth,
  startOfWeek,
} from "date-fns";
import { Views, type View } from "react-big-calendar";

export const PLANNER_WEEK_STARTS_ON = 1 as const; // Monday — matches PlannerCalendar ranges

export type NavRange = { start: Date; end: Date };

/** Snap an arbitrary day span to whole weeks (Mon–Sun). */
export function snapToWeekRange(from: Date, to: Date = from): NavRange {
  const a = from.getTime() <= to.getTime() ? from : to;
  const b = from.getTime() <= to.getTime() ? to : from;
  return {
    start: startOfWeek(a, { weekStartsOn: PLANNER_WEEK_STARTS_ON }),
    end: endOfWeek(b, { weekStartsOn: PLANNER_WEEK_STARTS_ON }),
  };
}

export function weekContaining(day: Date): NavRange {
  return snapToWeekRange(day, day);
}

/** True when selection spans more than one RBC week (7 days). */
export function isMultiWeekRange(range: NavRange | null | undefined): boolean {
  if (!range) return false;
  return differenceInCalendarDays(range.end, range.start) > 6;
}

/**
 * Label for the center date chip.
 * Multi-week nav ranges (Week mode) use an explicit span; otherwise label follows view.
 */
export function formatDateChipLabel(
  view: View,
  date: Date,
  navRange: NavRange | null,
): string {
  if (view === Views.DAY) {
    return format(date, "EEEE MMM d");
  }
  if (view === Views.MONTH) {
    return format(date, "MMMM yyyy");
  }
  // Week
  if (navRange && isMultiWeekRange(navRange)) {
    const { start, end } = navRange;
    if (isSameMonth(start, end)) {
      return `${format(start, "MMM d")}–${format(end, "d")}`;
    }
    return `${format(start, "MMM d")} – ${format(end, "MMM d")}`;
  }
  const start = startOfWeek(date, { weekStartsOn: PLANNER_WEEK_STARTS_ON });
  const end = endOfWeek(date, { weekStartsOn: PLANNER_WEEK_STARTS_ON });
  if (isSameMonth(start, end)) {
    return `${format(start, "MMM d")}–${format(end, "d")}`;
  }
  return `${format(start, "MMM d")}–${format(end, "MMM d")}`;
}
