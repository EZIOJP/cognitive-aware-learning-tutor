import { useCallback, useEffect, useState } from "react";
import { Filter, ListTree } from "lucide-react";
import {
  fetchActivities,
  type ActivityRow,
  type ActivitiesResponse,
} from "../../api/behaviorClient";
import { formatHoursMins } from "../../utils/formatDuration";
import { scoreColor } from "./GlanceBar";

type Props = {
  day?: string;
  trackerNoData?: boolean;
  refreshKey?: number;
};

export function ActivitiesPanel({ day, trackerNoData = false, refreshKey = 0 }: Props) {
  const [data, setData] = useState<ActivitiesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [uncategorizedOnly, setUncategorizedOnly] = useState(false);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const res = await fetchActivities(day, uncategorizedOnly);
      setData(res);
      setError(null);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load activities");
    } finally {
      setLoading(false);
    }
  }, [day, uncategorizedOnly]);

  useEffect(() => {
    void load();
  }, [load, refreshKey]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold flex items-center gap-2 text-sm">
            <ListTree size={16} className="text-primary" />
            Activities
          </h3>
          <p className="mt-1 text-sm text-muted-foreground">
            Ranked apps and sites from the desktop tracker — fix uncategorized items in Classification review below.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setUncategorizedOnly((v) => !v)}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs border ${
            uncategorizedOnly
              ? "border-amber-500/50 bg-amber-500/15 text-amber-100"
              : "border-white/10 bg-black/30 text-muted-foreground hover:text-foreground"
          }`}
        >
          <Filter size={12} />
          {uncategorizedOnly ? "Uncategorized only" : "All activities"}
          {data && data.uncategorized_count > 0 ? (
            <span className="tabular-nums opacity-80">({data.uncategorized_count})</span>
          ) : null}
        </button>
      </div>

      {trackerNoData && (
        <p className="text-xs text-amber-200/90 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2">
          No tracker data yet — start the desktop tracker to populate activities.
        </p>
      )}

      {error && <p className="text-xs text-rose-300">{error}</p>}

      {loading ? (
        <p className="text-xs text-muted-foreground">Loading activities…</p>
      ) : !data || data.activities.length === 0 ? (
        <p className="text-xs text-muted-foreground py-4 text-center">
          {uncategorizedOnly ? "No uncategorized activities — nice work." : "No activities logged for this day."}
        </p>
      ) : (
        <div className="rounded-xl border border-white/10 overflow-hidden">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-white/10 bg-black/30 text-muted-foreground text-left">
                <th className="px-3 py-2 font-medium">Activity</th>
                <th className="px-3 py-2 font-medium w-20 text-right">Time</th>
                <th className="px-3 py-2 font-medium w-16 text-right">Score</th>
                <th className="px-3 py-2 font-medium hidden sm:table-cell">Category</th>
              </tr>
            </thead>
            <tbody>
              {data.activities.map((row: ActivityRow) => (
                <tr key={row.key} className="border-b border-white/5 hover:bg-white/[0.03]">
                  <td className="px-3 py-2">
                    <div className="font-medium text-foreground truncate max-w-[14rem] sm:max-w-none">
                      {row.label}
                    </div>
                    {row.kind === "site" && row.parent ? (
                      <div className="text-[10px] text-muted-foreground truncate">{row.parent}</div>
                    ) : null}
                    {row.uncategorized ? (
                      <span className="text-[10px] text-amber-300/90">uncategorized</span>
                    ) : null}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums text-muted-foreground">
                    {formatHoursMins(Math.round(row.seconds / 60))}
                  </td>
                  <td className={`px-3 py-2 text-right tabular-nums font-semibold ${scoreColor(row.productivity_score)}`}>
                    {row.productivity_score}
                  </td>
                  <td className="px-3 py-2 hidden sm:table-cell text-muted-foreground truncate max-w-[10rem]">
                    {row.category}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default ActivitiesPanel;
