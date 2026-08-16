import { useState } from "react";
import {
  CalendarDays,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { Views, type View } from "react-big-calendar";
import { cn } from "../../app/components/ui/utils";
import { MiniCalendarPopover } from "./MiniCalendarPopover";
import {
  formatDateChipLabel,
  type NavRange,
} from "./miniCalendarUtils";

export type PlannerToolbarProps = {
  date: Date;
  view: View;
  views: View[] | Record<string, boolean>;
  label: string;
  onNavigate: (action: "PREV" | "NEXT" | "TODAY" | "DATE", newDate?: Date) => void;
  onView: (view: View) => void;
  /** Multi-week (or custom) navigation highlight — not KPI export */
  navRange: NavRange | null;
  onNavRangeChange: (range: NavRange | null) => void;
};

function resolveViewList(views: PlannerToolbarProps["views"]): View[] {
  if (Array.isArray(views)) return views as View[];
  return (Object.keys(views) as View[]).filter((k) => views[k]);
}

const VIEW_META: {
  view: View;
  letter: string;
  label: string;
}[] = [
  { view: Views.DAY, letter: "D", label: "Day" },
  { view: Views.WEEK, letter: "W", label: "Week" },
  { view: Views.MONTH, letter: "M", label: "Month" },
];

/**
 * Replaces default RBC toolbar: one left cluster of
 * ‹ › Today + date chip (mini-cal) + D|W|M letter pills.
 *
 * Multi-week ranges (Week mode): RBC Week stays 7 days; we navigate to range
 * start and keep the full span on the chip + mini-cal highlight.
 */
export function PlannerCalendarToolbar({
  date,
  view,
  views,
  onNavigate,
  onView,
  navRange,
  onNavRangeChange,
}: PlannerToolbarProps) {
  const [miniOpen, setMiniOpen] = useState(false);
  const viewList = resolveViewList(views);
  const chipLabel = formatDateChipLabel(view, date, navRange);

  const clearRangeAnd = (fn: () => void) => {
    onNavRangeChange(null);
    fn();
  };

  const goDate = (next: Date, nextView?: View, range?: NavRange | null) => {
    if (range !== undefined) onNavRangeChange(range);
    if (nextView) onView(nextView);
    onNavigate("DATE", next);
  };

  return (
    <div className="rbc-toolbar planner-cal-toolbar">
      <div className="planner-cal-toolbar__cluster">
        <div className="planner-cal-toolbar__nav-group" role="group" aria-label="Navigate">
          <button
            type="button"
            aria-label="Previous"
            title="Previous"
            className="planner-cal-toolbar__icon-btn"
            onClick={() => clearRangeAnd(() => onNavigate("PREV"))}
          >
            <ChevronLeft size={14} />
          </button>
          <button
            type="button"
            aria-label="Next"
            title="Next"
            className="planner-cal-toolbar__icon-btn"
            onClick={() => clearRangeAnd(() => onNavigate("NEXT"))}
          >
            <ChevronRight size={14} />
          </button>
          <button
            type="button"
            className="planner-cal-toolbar__today"
            onClick={() => clearRangeAnd(() => onNavigate("TODAY"))}
          >
            Today
          </button>
        </div>

        <MiniCalendarPopover
          open={miniOpen}
          onOpenChange={setMiniOpen}
          date={date}
          view={view}
          navRange={navRange}
          onPickDay={(day) => {
            goDate(day, Views.DAY, null);
          }}
          onPickMonth={(day) => {
            goDate(day, Views.MONTH, null);
          }}
          onPickWeekRange={(range) => {
            goDate(range.start, Views.WEEK, range);
          }}
          onGoToday={() => {
            clearRangeAnd(() => onNavigate("TODAY"));
          }}
          onClearRange={() => {
            onNavRangeChange(null);
          }}
        >
          <button
            type="button"
            className="planner-cal-toolbar__chip"
            aria-expanded={miniOpen}
            aria-haspopup="dialog"
          >
            <CalendarDays size={13} className="opacity-70" />
            <span>{chipLabel}</span>
          </button>
        </MiniCalendarPopover>

        <div
          className="planner-cal-toolbar__views"
          role="group"
          aria-label="Calendar view"
        >
          {VIEW_META.filter((m) => viewList.includes(m.view)).map((m) => {
            const active = view === m.view;
            return (
              <button
                key={m.view}
                type="button"
                title={m.label}
                aria-label={m.label}
                aria-pressed={active}
                className={cn(
                  "planner-cal-toolbar__view-pill",
                  active && "planner-cal-toolbar__view-pill--active",
                )}
                onClick={() => {
                  clearRangeAnd(() => onView(m.view));
                }}
              >
                {m.letter}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
