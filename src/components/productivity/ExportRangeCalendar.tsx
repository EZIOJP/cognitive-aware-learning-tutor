import { useEffect, useMemo, useState } from "react";
import {
  endOfMonth,
  endOfWeek,
  format,
  isAfter,
  startOfDay,
  startOfMonth,
  startOfWeek,
} from "date-fns";
import type { DateRange } from "react-day-picker";
import { Calendar } from "../../app/components/ui/calendar";
import { fetchExportDayPresence } from "../../api/plannerClient";
import { cn } from "../../app/components/ui/utils";
import { PLANNER_WEEK_STARTS_ON } from "./miniCalendarUtils";

type Props = {
  startIso: string;
  endIso: string;
  onRangeChange: (startIso: string, endIso: string) => void;
  className?: string;
};

function toIso(d: Date): string {
  return format(d, "yyyy-MM-dd");
}

function parseIso(iso: string): Date {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, (m || 1) - 1, d || 1);
}

/** Inclusive calendar bounds for the visible DayPicker month (incl. outside days). */
export function exportVisibleMonthBounds(month: Date): { start: string; end: string } {
  const start = startOfWeek(startOfMonth(month), {
    weekStartsOn: PLANNER_WEEK_STARTS_ON,
  });
  const end = endOfWeek(endOfMonth(month), {
    weekStartsOn: PLANNER_WEEK_STARTS_ON,
  });
  return { start: toIso(start), end: toIso(end) };
}

/** Empty (no tracked/plan/wearable) past/today days are muted in the grid. */
export function isExportDayMuted(
  iso: string,
  presence: ReadonlySet<string>,
  todayIso: string,
): boolean {
  if (iso > todayIso) return false;
  return !presence.has(iso);
}

/**
 * Month grid for productivity export from→to.
 * Days with tracked/plan/wearable data are emphasized; empty days are faded
 * but stay selectable (include-empty can keep them in the download).
 */
export function ExportRangeCalendar({
  startIso,
  endIso,
  onRangeChange,
  className,
}: Props) {
  const selected = useMemo<DateRange>(
    () => ({ from: parseIso(startIso), to: parseIso(endIso) }),
    [startIso, endIso],
  );
  const [month, setMonth] = useState(() => parseIso(endIso));
  const [presence, setPresence] = useState<Set<string>>(() => new Set());
  const [presenceError, setPresenceError] = useState<string | null>(null);
  const [loadingPresence, setLoadingPresence] = useState(false);

  const today = startOfDay(new Date());
  const todayIso = toIso(today);

  useEffect(() => {
    setMonth(parseIso(endIso));
  }, [endIso]);

  useEffect(() => {
    const { start, end } = exportVisibleMonthBounds(month);
    let cancelled = false;
    setLoadingPresence(true);
    setPresenceError(null);
    void (async () => {
      try {
        const res = await fetchExportDayPresence(start, end);
        if (cancelled) return;
        setPresence(new Set(res.days));
      } catch (e: unknown) {
        if (cancelled) return;
        setPresence(new Set());
        setPresenceError(e instanceof Error ? e.message : "Could not load day markers");
      } finally {
        if (!cancelled) setLoadingPresence(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [month]);

  const monthPresenceCount = useMemo(() => {
    const y = month.getFullYear();
    const m = month.getMonth();
    let n = 0;
    for (const iso of presence) {
      const d = parseIso(iso);
      if (d.getFullYear() === y && d.getMonth() === m) n += 1;
    }
    return n;
  }, [month, presence]);

  return (
    <div
      className={cn(
        "rounded-xl border border-white/10 bg-black/20 p-2",
        className,
      )}
    >
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2 px-1">
        <p className="text-[10px] text-muted-foreground">
          Pick from → to.{" "}
          <span className="text-foreground/80">Emphasized</span> days have data;{" "}
          <span className="opacity-40">faded</span> days are empty (still selectable).
        </p>
        {loadingPresence && (
          <span className="text-[10px] text-muted-foreground">Loading…</span>
        )}
      </div>
      <Calendar
        mode="range"
        month={month}
        onMonthChange={setMonth}
        selected={selected}
        onSelect={(range) => {
          if (!range?.from) return;
          const from = startOfDay(range.from);
          const to = startOfDay(range.to ?? range.from);
          if (isAfter(from, today) || isAfter(to, today)) return;
          onRangeChange(toIso(from), toIso(to));
        }}
        weekStartsOn={PLANNER_WEEK_STARTS_ON}
        numberOfMonths={1}
        disabled={(d) => isAfter(startOfDay(d), today)}
        className="p-0"
        modifiers={{
          hasData: (d) => presence.has(toIso(d)),
          noData: (d) => {
            const iso = toIso(d);
            return isExportDayMuted(iso, presence, todayIso);
          },
        }}
        modifiersClassNames={{
          hasData:
            "font-semibold text-primary ring-1 ring-inset ring-primary/45 bg-primary/15",
          noData: "opacity-35 text-muted-foreground",
        }}
        classNames={{
          day_selected:
            "bg-primary text-primary-foreground hover:bg-primary hover:text-primary-foreground focus:bg-primary focus:text-primary-foreground opacity-100",
          day_range_middle:
            "aria-selected:bg-primary/25 aria-selected:text-foreground opacity-100",
          day_today: "border border-primary/40",
        }}
      />
      {presenceError && (
        <p className="mt-1 px-1 text-[10px] text-amber-300/90" title={presenceError}>
          Markers unavailable — range pick still works.
        </p>
      )}
      <div className="mt-2 flex flex-wrap gap-3 px-1 text-[10px] text-muted-foreground">
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block size-2.5 rounded-sm bg-primary/40 ring-1 ring-primary/50" />
          Has data{monthPresenceCount > 0 ? ` (${monthPresenceCount})` : ""}
        </span>
        <span className="inline-flex items-center gap-1.5 opacity-50">
          <span className="inline-block size-2.5 rounded-sm bg-muted-foreground/40" />
          Empty
        </span>
        <span>
          {startIso}
          {startIso !== endIso ? ` → ${endIso}` : ""}
        </span>
      </div>
    </div>
  );
}
