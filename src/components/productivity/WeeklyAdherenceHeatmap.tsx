import type { AdherenceDay } from "./planVsActualUtils";

type Props = {
  days: AdherenceDay[];
  selectedDay: Date;
  onSelectDay: (d: Date) => void;
  loading?: boolean;
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

export function WeeklyAdherenceHeatmap({ days, selectedDay, onSelectDay, loading }: Props) {
  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4 space-y-3 flex-1 min-w-0">
      <h3 className="font-medium text-sm">Weekly adherence</h3>
      {loading ? (
        <div className="grid grid-cols-7 gap-2">
          {[...Array(7)].map((_, i) => (
            <div key={i} className="h-14 rounded-lg bg-white/5 animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-7 gap-2">
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
                className={`flex flex-col items-center justify-center gap-0.5 py-2 px-1 rounded-lg border text-xs transition-colors hover:brightness-110 ${cellClass(d)} ${selected ? "ring-2 ring-violet-400/60" : ""}`}
              >
                <span className="font-medium">{weekdayLabel(d.date)}</span>
                <span className="text-lg font-bold tabular-nums">
                  {d.noPlan || d.pct == null ? "–" : `${Math.round(d.pct)}%`}
                </span>
              </button>
            );
          })}
        </div>
      )}
      <p className="text-[10px] text-muted-foreground">
        Green ≥75% · Amber 40–74% · Red &lt;40% · Gray = no plan
      </p>
    </div>
  );
}

export default WeeklyAdherenceHeatmap;
