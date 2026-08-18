import { useCallback, useEffect, useState } from "react";
import { BarChart3, Flame, Target } from "lucide-react";
import { fetchWeeklyDigest, type WeeklyDigestResponse } from "../../api/behaviorClient";
import { formatHoursMins } from "../../utils/formatDuration";
import { scoreColor } from "./GlanceBar";

type Props = {
  endDay?: string;
  days?: number;
  refreshKey?: number;
};

export function WeeklyDigestPanel({ endDay, days = 7, refreshKey = 0 }: Props) {
  const [data, setData] = useState<WeeklyDigestResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setData(await fetchWeeklyDigest(days, endDay));
      setError(null);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load digest");
    } finally {
      setLoading(false);
    }
  }, [days, endDay]);

  useEffect(() => {
    void load();
  }, [load, refreshKey]);

  if (loading) {
    return <p className="text-xs text-muted-foreground">Loading weekly digest…</p>;
  }
  if (error) {
    return <p className="text-xs text-rose-300">{error}</p>;
  }
  if (!data) return null;

  return (
    <div className="space-y-4">
      <div>
        <h3 className="font-semibold text-sm flex items-center gap-2">
          <BarChart3 size={16} className="text-primary" />
          Weekly digest
        </h3>
        <p className="text-xs text-muted-foreground mt-1">
          {data.from} → {data.to} · local tracker data
        </p>
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        <div className="rounded-xl border border-white/10 bg-black/25 p-3">
          <div className={`text-2xl font-bold tabular-nums ${scoreColor(data.avg_pulse)}`}>
            {data.avg_pulse}
          </div>
          <div className="text-[10px] uppercase tracking-wider text-muted-foreground mt-1">Avg pulse</div>
        </div>
        <div className="rounded-xl border border-white/10 bg-black/25 p-3">
          <div className="text-2xl font-bold tabular-nums text-emerald-300">
            {data.goal_met_days}/{data.tracked_days || days}
          </div>
          <div className="text-[10px] uppercase tracking-wider text-muted-foreground mt-1 flex items-center gap-1">
            <Target size={10} /> Goal days
          </div>
        </div>
        <div className="rounded-xl border border-white/10 bg-black/25 p-3">
          <div className="text-2xl font-bold tabular-nums text-amber-200">{data.top_drains.length}</div>
          <div className="text-[10px] uppercase tracking-wider text-muted-foreground mt-1 flex items-center gap-1">
            <Flame size={10} /> Top drains
          </div>
        </div>
      </div>
      {data.top_drains.length > 0 ? (
        <ul className="text-xs space-y-1.5">
          {data.top_drains.map((d) => (
            <li key={d.label} className="flex justify-between gap-2 rounded-lg border border-white/10 bg-black/20 px-3 py-2">
              <span className="truncate">{d.label}</span>
              <span className="tabular-nums text-muted-foreground shrink-0">
                {formatHoursMins(Math.round(d.seconds / 60))}
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-xs text-muted-foreground">No low-score drains this week.</p>
      )}
    </div>
  );
}

export default WeeklyDigestPanel;
