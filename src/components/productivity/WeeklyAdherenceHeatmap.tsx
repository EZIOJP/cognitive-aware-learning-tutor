import { Flame } from "lucide-react";
import { computeStreak, type AdherenceDay } from "./planVsActualUtils";

type Props = {
  days: AdherenceDay[];
  selectedDay: Date;
  onSelectDay: (d: Date) => void;
  loading?: boolean;
  /** Adherence % threshold for streak (0–1). Default 0.7 */
  streakThreshold?: number;
};

function cellClass(d: AdherenceDay): string {
  if (d.noPlan || d.pct == null) {
    return "bg-white/5 text-muted-foreground border-white/10";
  }
  if (d.pct >= 75) return "bg-emerald-500/25 text-emerald-300 border-emerald-500/40";
  if (d.pct >= 40) return "bg-amber-500/25 text-amber-300 border-amber-500/40";
  return "bg-red-500/25 text-red-300 border-red-500/40";
}

function weekdayLabel(dateStr: string): string {
  const [y, m, d] = dateStr.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString(undefined, { weekday: "short" });
}

function isSameDay(a: Date, dateStr: string): boolean {
  const [y, m, d] = dateStr.split("-").map(Number);
  return a.getFullYear() === y && a.getMonth() === m - 1 && a.getDate() === d;
}

/**
 * Flush week strip — no outer card. Streak badge inline at end of row.
 */
export function WeeklyAdherenceHeatmap({
  days,
  selectedDay,
  onSelectDay,
  loading,
  streakThreshold = 0.7,
}: Props) {
  const streak = computeStreak(days, streakThreshold);
  const pctLabel = Math.round(streakThreshold * 100);

  return (
    <div className="space-y-2 min-w-0 flex-1">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
          Weekly adherence
        </h3>
        <span
          className="inline-flex items-center gap-1.5 rounded-full border border-orange-500/30 bg-orange-500/10 px-2.5 py-0.5 text-xs tabular-nums text-orange-200"
          title={`Days in a row at ≥${pctLabel}% on planned days`}
        >
          <Flame size={12} className="text-orange-400" aria-hidden />
          {loading ? "…" : (
            <>
              <span className="font-bold">{streak}</span>
              <span className="text-[10px] text-orange-200/70">
                day{streak === 1 ? "" : "s"} ≥{pctLabel}%
              </span>
            </>
          )}
        </span>
      </div>
      {loading ? (
        <div className="grid grid-cols-7 gap-2">
          {[...Array(7)].map((_, i) => (
            <div key={i} className="h-12 rounded-lg bg-white/5 animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-7 gap-1.5 sm:gap-2">
          {days.map((d) => {
            const selected = isSameDay(selectedDay, d.date);
            return (
              <button
                key={d.date}
                type="button"
                onClick={() => {
                  const [y, m, day] = d.date.split("-").map(Number);
                  onSelectDay(new Date(y, m - 1, day));
                }}
                className={`flex flex-col items-center justify-center gap-0.5 py-1.5 px-0.5 rounded-lg border text-[10px] sm:text-xs transition-colors hover:brightness-110 ${cellClass(d)} ${selected ? "ring-2 ring-violet-400/60" : ""}`}
              >
                <span className="font-medium opacity-80">{weekdayLabel(d.date)}</span>
                <span className="text-base sm:text-lg font-bold tabular-nums leading-none">
                  {d.noPlan || d.pct == null ? "–" : `${Math.round(d.pct)}%`}
                </span>
              </button>
            );
          })}
        </div>
      )}
      <p className="text-[10px] text-muted-foreground">
        On-plan focus % · Green ≥75% · Amber 40–74% · Red &lt;40% · Gray = no plan
      </p>
    </div>
  );
}

export default WeeklyAdherenceHeatmap;
