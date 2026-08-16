import { useEffect, useRef, useState } from "react";
import { format, isSameDay, isWithinInterval, startOfDay } from "date-fns";
import { ChevronLeft, ChevronRight } from "lucide-react";
import type { CaptionLabelProps } from "react-day-picker";
import { Views, type View } from "react-big-calendar";
import { Calendar } from "../../app/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "../../app/components/ui/popover";
import { cn } from "../../app/components/ui/utils";
import {
  isMultiWeekRange,
  PLANNER_WEEK_STARTS_ON,
  snapToWeekRange,
  weekContaining,
  type NavRange,
} from "./miniCalendarUtils";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  date: Date;
  view: View;
  navRange: NavRange | null;
  onPickDay: (day: Date) => void;
  onPickMonth: (day: Date) => void;
  onPickWeekRange: (range: NavRange) => void;
  onGoToday: () => void;
  onClearRange: () => void;
  children: React.ReactNode;
};

const NAV_BTN =
  "size-7 bg-transparent p-0 opacity-70 hover:opacity-100 rounded-md border border-white/10 text-muted-foreground hover:bg-white/5 hover:text-foreground inline-flex items-center justify-center";

/**
 * Year + 12-month grid for fast jumps from the caption label.
 * Selecting a month returns to the day grid; Escape / year label goes back.
 */
function MonthYearPicker({
  year,
  selectedMonth,
  onYearChange,
  onSelectMonth,
  onBack,
}: {
  year: number;
  selectedMonth: Date;
  onYearChange: (year: number) => void;
  onSelectMonth: (month: Date) => void;
  onBack: () => void;
}) {
  const today = new Date();

  return (
    <div
      className="min-w-[16.5rem]"
      role="dialog"
      aria-label="Choose month"
    >
      <div className="relative flex w-full items-center justify-center pt-0.5">
        <button
          type="button"
          className={cn(NAV_BTN, "absolute left-1")}
          aria-label="Previous year"
          onClick={() => onYearChange(year - 1)}
        >
          <ChevronLeft className="size-4" />
        </button>
        <button
          type="button"
          className="rounded-md px-1.5 py-0.5 text-xs font-medium text-foreground hover:bg-white/10 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary/60"
          aria-label={`Back to calendar for ${year}`}
          onClick={onBack}
        >
          {year}
        </button>
        <button
          type="button"
          className={cn(NAV_BTN, "absolute right-1")}
          aria-label="Next year"
          onClick={() => onYearChange(year + 1)}
        >
          <ChevronRight className="size-4" />
        </button>
      </div>

      <div
        className="mt-3 grid grid-cols-3 gap-1.5"
        role="listbox"
        aria-label={`Months in ${year}`}
      >
        {Array.from({ length: 12 }, (_, monthIndex) => {
          const candidate = new Date(year, monthIndex, 1);
          const selected =
            selectedMonth.getFullYear() === year &&
            selectedMonth.getMonth() === monthIndex;
          const isCurrent =
            today.getFullYear() === year && today.getMonth() === monthIndex;

          return (
            <button
              key={monthIndex}
              type="button"
              role="option"
              aria-selected={selected}
              className={cn(
                "rounded-md py-2 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary/60",
                selected
                  ? "bg-primary text-primary-foreground hover:bg-primary"
                  : isCurrent
                    ? "border border-primary/50 text-primary hover:bg-white/10"
                    : "text-foreground hover:bg-white/10",
              )}
              onClick={() => onSelectMonth(candidate)}
            >
              {format(candidate, "MMM")}
            </button>
          );
        })}
      </div>
    </div>
  );
}

/**
 * Mini calendar inside the date-chip popover.
 *
 * Week mode: first click selects that week; second click extends to a multi-week
 * span (snapped Mon–Sun). Drag (mouseenter while button held / touch move) also
 * extends. RBC Week stays 7 days — navigate to range start; chip + grid keep the
 * full span highlighted.
 *
 * Caption ("June 2026") opens a month/year picker for fast jumps; ‹ › still step
 * one month at a time.
 */
export function MiniCalendarPopover({
  open,
  onOpenChange,
  date,
  view,
  navRange,
  onPickDay,
  onPickMonth,
  onPickWeekRange,
  onGoToday,
  onClearRange,
  children,
}: Props) {
  const [month, setMonth] = useState(() => date);
  const [monthPickerOpen, setMonthPickerOpen] = useState(false);
  const [pickerYear, setPickerYear] = useState(() => date.getFullYear());
  const [weekHighlight, setWeekHighlight] = useState<NavRange | null>(null);
  const [weekAnchor, setWeekAnchor] = useState<Date | null>(null);

  const weekHighlightRef = useRef<NavRange | null>(null);
  weekHighlightRef.current = weekHighlight;
  const dragOriginRef = useRef<Date | null>(null);
  const touchStartRef = useRef<Date | null>(null);
  const skipClickRef = useRef(false);

  useEffect(() => {
    if (!open) {
      setMonthPickerOpen(false);
      return;
    }
    setMonth(date);
    if (view === Views.WEEK) {
      setWeekHighlight(navRange ?? weekContaining(date));
      setWeekAnchor(null);
      dragOriginRef.current = null;
      touchStartRef.current = null;
      skipClickRef.current = false;
    } else {
      setWeekHighlight(null);
      setWeekAnchor(null);
      dragOriginRef.current = null;
      touchStartRef.current = null;
    }
  }, [open, date, view, navRange]);

  useEffect(() => {
    if (monthPickerOpen) setPickerYear(month.getFullYear());
  }, [monthPickerOpen, month]);

  const multiActive =
    isMultiWeekRange(navRange) || isMultiWeekRange(weekHighlight);

  const commitDrag = () => {
    const origin = dragOriginRef.current;
    const highlight = weekHighlightRef.current;
    dragOriginRef.current = null;
    touchStartRef.current = null;
    if (!origin || !highlight) return;
    skipClickRef.current = true;
    setWeekHighlight(highlight);
    setWeekAnchor(null);
    onPickWeekRange(highlight);
    if (isMultiWeekRange(highlight)) onOpenChange(false);
  };

  const CaptionLabel = ({ id, displayMonth }: CaptionLabelProps) => (
    <button
      type="button"
      id={id}
      className={cn(
        "rounded-md px-1.5 py-0.5 text-xs font-medium text-foreground",
        "hover:bg-white/10 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary/60",
      )}
      aria-haspopup="dialog"
      aria-expanded={monthPickerOpen}
      aria-label={`Choose month, currently ${format(displayMonth, "MMMM yyyy")}`}
      onClick={(e) => {
        e.preventDefault();
        e.stopPropagation();
        setMonthPickerOpen(true);
      }}
    >
      {format(displayMonth, "MMMM yyyy")}
    </button>
  );

  const dayPickerClassNames = {
    months: "flex flex-col",
    month: "space-y-2",
    caption: "flex justify-center pt-0.5 relative items-center w-full",
    caption_label: "text-xs font-medium text-foreground",
    nav: "flex items-center gap-1",
    nav_button: NAV_BTN,
    nav_button_previous: "absolute left-1",
    nav_button_next: "absolute right-1",
    table: "w-full border-collapse",
    head_row: "flex",
    head_cell: "text-muted-foreground rounded-md w-8 font-normal text-[0.7rem]",
    row: "flex w-full mt-1",
    cell: cn(
      "relative p-0 text-center text-sm focus-within:relative focus-within:z-20",
      view === Views.WEEK
        ? "[&:has(.day-week-sel)]:bg-primary/15 first:[&:has(.day-week-sel)]:rounded-l-md last:[&:has(.day-week-sel)]:rounded-r-md"
        : "[&:has([aria-selected])]:rounded-md",
    ),
    day: "size-8 p-0 font-normal text-xs rounded-md text-foreground hover:bg-white/10 inline-flex items-center justify-center",
    day_selected:
      "bg-primary text-primary-foreground hover:bg-primary hover:text-primary-foreground focus:bg-primary focus:text-primary-foreground",
    day_today: "border border-primary/50 text-primary",
    day_outside: "text-muted-foreground/50",
    day_disabled: "text-muted-foreground opacity-50",
    day_hidden: "invisible",
  };

  const dayPickerComponents = { CaptionLabel };

  return (
    <Popover open={open} onOpenChange={onOpenChange}>
      <PopoverTrigger asChild>{children}</PopoverTrigger>
      <PopoverContent
        align="center"
        sideOffset={6}
        className="w-auto border-white/10 bg-popover/95 p-3 shadow-xl backdrop-blur-sm"
        onKeyDown={(e) => {
          if (e.key !== "Escape") return;
          if (monthPickerOpen) {
            e.preventDefault();
            e.stopPropagation();
            setMonthPickerOpen(false);
            return;
          }
          onOpenChange(false);
        }}
        onPointerUp={commitDrag}
      >
        {monthPickerOpen ? (
          <MonthYearPicker
            year={pickerYear}
            selectedMonth={month}
            onYearChange={setPickerYear}
            onSelectMonth={(next) => {
              setMonth(next);
              setMonthPickerOpen(false);
            }}
            onBack={() => setMonthPickerOpen(false)}
          />
        ) : view === Views.WEEK ? (
          <Calendar
            mode="default"
            month={month}
            onMonthChange={setMonth}
            weekStartsOn={PLANNER_WEEK_STARTS_ON}
            numberOfMonths={1}
            className="p-0"
            classNames={dayPickerClassNames}
            components={dayPickerComponents}
            modifiers={{
              weekSel: (d) => {
                if (!weekHighlight) return false;
                return isWithinInterval(startOfDay(d), {
                  start: startOfDay(weekHighlight.start),
                  end: startOfDay(weekHighlight.end),
                });
              },
              weekStart: (d) =>
                !!weekHighlight && isSameDay(d, weekHighlight.start),
              weekEnd: (d) =>
                !!weekHighlight && isSameDay(d, weekHighlight.end),
            }}
            modifiersClassNames={{
              weekSel: "day-week-sel bg-primary/30 text-foreground rounded-none",
              weekStart: "bg-primary text-primary-foreground rounded-l-md",
              weekEnd: "bg-primary text-primary-foreground rounded-r-md",
            }}
            onDayClick={(day, modifiers) => {
              if (modifiers.disabled) return;
              if (skipClickRef.current) {
                skipClickRef.current = false;
                return;
              }
              if (dragOriginRef.current) return;
              if (!weekAnchor) {
                const snapped = weekContaining(day);
                setWeekHighlight(snapped);
                setWeekAnchor(day);
                onPickWeekRange(snapped);
                return;
              }
              const final = snapToWeekRange(weekAnchor, day);
              setWeekHighlight(final);
              setWeekAnchor(null);
              onPickWeekRange(final);
              onOpenChange(false);
            }}
            onDayMouseEnter={(day, modifiers, e) => {
              if (modifiers.disabled) return;
              if (e.buttons !== 1) return;
              if (!dragOriginRef.current) {
                dragOriginRef.current = day;
                setWeekHighlight(weekContaining(day));
                return;
              }
              setWeekHighlight(snapToWeekRange(dragOriginRef.current, day));
            }}
            onDayTouchStart={(day, modifiers) => {
              if (modifiers.disabled) return;
              // Defer drag origin until move so a simple tap uses onDayClick
              dragOriginRef.current = null;
              touchStartRef.current = day;
            }}
            onDayTouchMove={(day, modifiers) => {
              if (modifiers.disabled) return;
              const start = dragOriginRef.current ?? touchStartRef.current;
              if (!start) return;
              dragOriginRef.current = start;
              setWeekHighlight(snapToWeekRange(start, day));
            }}
          />
        ) : (
          <Calendar
            mode="single"
            month={month}
            onMonthChange={setMonth}
            weekStartsOn={PLANNER_WEEK_STARTS_ON}
            selected={date}
            numberOfMonths={1}
            className="p-0"
            classNames={dayPickerClassNames}
            components={dayPickerComponents}
            onSelect={(day) => {
              if (!day) return;
              if (view === Views.MONTH) {
                onPickMonth(day);
              } else {
                onPickDay(day);
              }
              onOpenChange(false);
            }}
          />
        )}

        <div className="mt-2 flex items-center justify-between gap-2 border-t border-white/10 pt-2">
          <button
            type="button"
            className="rounded-md px-2 py-1 text-[11px] text-muted-foreground hover:bg-white/5 hover:text-foreground"
            onClick={() => {
              onGoToday();
              onOpenChange(false);
            }}
          >
            Today
          </button>
          {multiActive ? (
            <button
              type="button"
              className="rounded-md px-2 py-1 text-[11px] text-muted-foreground hover:bg-white/5 hover:text-foreground"
              onClick={() => {
                onClearRange();
                setWeekHighlight(weekContaining(date));
                setWeekAnchor(null);
                dragOriginRef.current = null;
                touchStartRef.current = null;
                skipClickRef.current = false;
              }}
            >
              Clear range
            </button>
          ) : (
            <span className="text-[10px] text-muted-foreground/70">
              {monthPickerOpen
                ? "Pick a month · Esc back"
                : view === Views.WEEK
                  ? "Click week · drag/click to extend"
                  : "Pick a date"}
            </span>
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}
