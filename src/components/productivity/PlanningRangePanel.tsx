import { useMemo, useState } from "react";
import { CalendarDays, Loader2, Trash2 } from "lucide-react";
import {
  addDays,
  differenceInCalendarDays,
  endOfMonth,
  endOfWeek,
  format,
  isBefore,
  startOfDay,
} from "date-fns";
import type { DateRange } from "react-day-picker";
import {
  applyRoutinesRange,
  clearPlannerRange,
  expandYmdRange,
  MAX_ROUTINE_APPLY_DAYS,
} from "../../api/plannerClient";
import { Calendar } from "../../app/components/ui/calendar";
import { cn } from "../../app/components/ui/utils";
import { PLANNER_WEEK_STARTS_ON } from "./miniCalendarUtils";

type HorizonPreset = "today" | "week" | "month" | "custom";

function ymdLocal(d: Date): string {
  return format(startOfDay(d), "yyyy-MM-dd");
}

function parseYmd(iso: string): Date {
  const [y, m, d] = iso.split("-").map(Number);
  return startOfDay(new Date(y, (m || 1) - 1, d || 1));
}

function clampRangeFromToday(from: Date, to: Date): { from: Date; to: Date } {
  const today = startOfDay(new Date());
  let a = startOfDay(from);
  let b = startOfDay(to);
  if (a.getTime() > b.getTime()) {
    const t = a;
    a = b;
    b = t;
  }
  if (isBefore(a, today)) a = today;
  if (isBefore(b, a)) b = a;
  const span = differenceInCalendarDays(b, a) + 1;
  if (span > MAX_ROUTINE_APPLY_DAYS) {
    b = addDays(a, MAX_ROUTINE_APPLY_DAYS - 1);
  }
  return { from: a, to: b };
}

/**
 * Lock a planning date range and apply / clear routine-backed plan blocks.
 * Lives on Plan → Range (not Routines or Goals).
 */
export function PlanningRangePanel({ onApplied }: { onApplied?: () => void }) {
  const [locking, setLocking] = useState(false);
  const [clearingRange, setClearingRange] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [horizon, setHorizon] = useState<HorizonPreset>("today");
  const [rangeStart, setRangeStart] = useState(() => ymdLocal(new Date()));
  const [rangeEnd, setRangeEnd] = useState(() => ymdLocal(new Date()));
  const [calMonth, setCalMonth] = useState(() => startOfDay(new Date()));

  const selectedRange = useMemo<DateRange>(
    () => ({ from: parseYmd(rangeStart), to: parseYmd(rangeEnd) }),
    [rangeStart, rangeEnd],
  );
  const rangeDates = useMemo(
    () => expandYmdRange(rangeStart, rangeEnd),
    [rangeStart, rangeEnd],
  );
  const rangeLabel =
    rangeStart === rangeEnd ? rangeStart : `${rangeStart} → ${rangeEnd}`;

  const busy = locking || clearingRange;

  const applyPreset = (preset: HorizonPreset) => {
    const today = startOfDay(new Date());
    setHorizon(preset);
    if (preset === "today") {
      const y = ymdLocal(today);
      setRangeStart(y);
      setRangeEnd(y);
      setCalMonth(today);
      return;
    }
    if (preset === "week") {
      const from = today;
      const to = endOfWeek(today, { weekStartsOn: PLANNER_WEEK_STARTS_ON });
      const clamped = clampRangeFromToday(from, to);
      setRangeStart(ymdLocal(clamped.from));
      setRangeEnd(ymdLocal(clamped.to));
      setCalMonth(clamped.from);
      return;
    }
    if (preset === "month") {
      const from = today;
      const to = endOfMonth(today);
      const clamped = clampRangeFromToday(from, to);
      setRangeStart(ymdLocal(clamped.from));
      setRangeEnd(ymdLocal(clamped.to));
      setCalMonth(clamped.from);
    }
  };

  const handleLockIn = async () => {
    if (!rangeDates.length) return;
    setLocking(true);
    setError(null);
    setStatus(null);
    try {
      const r = await applyRoutinesRange(rangeDates);
      onApplied?.();
      setStatus(
        `Applied ${r.created} block${r.created === 1 ? "" : "s"} across ${r.days} day${r.days === 1 ? "" : "s"} in this planning range.`,
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not apply planning range");
    } finally {
      setLocking(false);
    }
  };

  const handleClearRange = async () => {
    if (!rangeDates.length) return;
    if (
      !confirm(
        `Delete all plan blocks for ${rangeDates.length} day${rangeDates.length === 1 ? "" : "s"} (${rangeLabel})? Routines stay.`,
      )
    ) {
      return;
    }
    setClearingRange(true);
    setError(null);
    setStatus(null);
    try {
      const r = await clearPlannerRange(rangeDates);
      onApplied?.();
      setStatus(
        `Cleared ${r.deleted} block${r.deleted === 1 ? "" : "s"} across ${r.days} day${r.days === 1 ? "" : "s"}.`,
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Clear range failed");
    } finally {
      setClearingRange(false);
    }
  };

  return (
    <div className="rounded-xl border border-white/10 bg-black/20 p-3 space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-medium flex items-center gap-1.5">
          <CalendarDays size={14} className="text-amber-400/90" />
          Planning range
        </h3>
        <span className="text-[11px] text-muted-foreground tabular-nums">{rangeLabel}</span>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {(
          [
            ["today", "Today"],
            ["week", "This week"],
            ["month", "This month"],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            disabled={busy}
            onClick={() => applyPreset(id)}
            className={cn(
              "px-2.5 py-1 rounded-md text-[11px] border transition-colors disabled:opacity-50",
              horizon === id
                ? "bg-amber-500/20 border-amber-400/40 text-amber-100"
                : "bg-white/5 border-white/10 text-muted-foreground hover:bg-white/10",
            )}
          >
            {label}
          </button>
        ))}
      </div>
      <Calendar
        mode="range"
        month={calMonth}
        onMonthChange={setCalMonth}
        selected={selectedRange}
        onSelect={(range) => {
          if (!range?.from) return;
          const clamped = clampRangeFromToday(range.from, range.to ?? range.from);
          setHorizon("custom");
          setRangeStart(ymdLocal(clamped.from));
          setRangeEnd(ymdLocal(clamped.to));
        }}
        weekStartsOn={PLANNER_WEEK_STARTS_ON}
        numberOfMonths={1}
        disabled={(d) => isBefore(startOfDay(d), startOfDay(new Date()))}
        className="p-0"
        classNames={{
          day_selected:
            "bg-amber-500 text-amber-950 hover:bg-amber-500 hover:text-amber-950 focus:bg-amber-500 focus:text-amber-950 opacity-100",
          day_range_middle:
            "aria-selected:bg-amber-500/25 aria-selected:text-foreground opacity-100",
          day_today: "border border-amber-400/40",
        }}
      />
      <p className="text-[10px] text-muted-foreground">
        From today · max {MAX_ROUTINE_APPLY_DAYS} days · weekday masks still apply.
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          disabled={busy || rangeDates.length === 0}
          onClick={() => void handleLockIn()}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-600/80 hover:bg-amber-600 text-xs font-medium disabled:opacity-50"
        >
          {locking ? <Loader2 size={13} className="animate-spin" /> : <CalendarDays size={13} />}
          Apply range
          {rangeDates.length > 1 ? ` (${rangeDates.length} days)` : ""}
        </button>
        <button
          type="button"
          disabled={busy || rangeDates.length === 0}
          onClick={() => void handleClearRange()}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/5 hover:bg-rose-500/20 text-xs border border-white/10 text-rose-200/90 disabled:opacity-50"
        >
          {clearingRange ? <Loader2 size={13} className="animate-spin" /> : <Trash2 size={13} />}
          Clear range days
        </button>
      </div>
      {error && (
        <p className="text-sm text-red-300 bg-red-500/10 border border-red-500/30 rounded-lg px-3 py-2">
          {error}
        </p>
      )}
      {status && (
        <p className="text-[11px] text-emerald-200/90" role="status">
          {status}
        </p>
      )}
    </div>
  );
}

export default PlanningRangePanel;
