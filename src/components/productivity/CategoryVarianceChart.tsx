import { useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { fetchTimetables } from "../../api/timetableClient";
import { useActualOverlay, usePlannerBlocks } from "../../hooks/usePlanVsActual";
import {
  aggregateActualByCategory,
  aggregatePlannedByTask,
  endOfWeekSunday,
  startOfWeekMonday,
} from "./planVsActualUtils";

type RangePreset = "today" | "week" | "last7";

type Props = {
  from?: Date;
  to?: Date;
};

function buildTaskMap(timetables: Awaited<ReturnType<typeof fetchTimetables>>): Map<number, string> {
  const map = new Map<number, string>();
  for (const tt of timetables.timetables) {
    for (const task of tt.tasks) {
      map.set(task.id, task.title);
    }
  }
  return map;
}

function ChartPanel({
  title,
  data,
  color,
  emptyMessage,
}: {
  title: string;
  data: { name: string; hours: number }[];
  color: string;
  emptyMessage: string;
}) {
  if (data.length === 0) {
    return (
      <div className="space-y-2">
        <h4 className="text-xs font-medium text-muted-foreground">{title}</h4>
        <p className="text-sm text-muted-foreground py-6 text-center">{emptyMessage}</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <h4 className="text-xs font-medium text-muted-foreground">{title}</h4>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 48 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
          <XAxis
            dataKey="name"
            tick={{ fill: "rgba(255,255,255,0.5)", fontSize: 10 }}
            angle={-35}
            textAnchor="end"
            height={56}
            interval={0}
          />
          <YAxis
            tick={{ fill: "rgba(255,255,255,0.5)", fontSize: 10 }}
            label={{ value: "Hours", angle: -90, position: "insideLeft", fill: "rgba(255,255,255,0.4)", fontSize: 10 }}
          />
          <Tooltip
            contentStyle={{
              background: "rgba(15,15,20,0.95)",
              border: "1px solid rgba(255,255,255,0.1)",
              borderRadius: 8,
              fontSize: 12,
            }}
            formatter={(v: number) => [`${v}h`, "Hours"]}
          />
          <Bar dataKey="hours" fill={color} radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function CategoryVarianceChart({ from: fromProp, to: toProp }: Props) {
  const [preset, setPreset] = useState<RangePreset>("today");
  const [taskMap, setTaskMap] = useState<Map<number, string>>(new Map());

  const { from, to } = useMemo(() => {
    if (fromProp && toProp) return { from: fromProp, to: toProp };
    const now = new Date();
    if (preset === "today") {
      const start = new Date(now);
      start.setHours(0, 0, 0, 0);
      const end = new Date(now);
      end.setHours(23, 59, 59, 999);
      return { from: start, to: end };
    }
    if (preset === "week") {
      return { from: startOfWeekMonday(now), to: endOfWeekSunday(now) };
    }
    const end = new Date(now);
    end.setHours(23, 59, 59, 999);
    const start = new Date(now);
    start.setDate(start.getDate() - 6);
    start.setHours(0, 0, 0, 0);
    return { from: start, to: end };
  }, [fromProp, toProp, preset]);

  const { data: blocks, loading: blocksLoading } = usePlannerBlocks(from, to);
  const { data: sessions, loading: sessionsLoading } = useActualOverlay(from, to);

  useEffect(() => {
    fetchTimetables()
      .then((res) => setTaskMap(buildTaskMap(res)))
      .catch(() => setTaskMap(new Map()));
  }, []);

  const plannedData = useMemo(
    () => aggregatePlannedByTask(blocks, taskMap),
    [blocks, taskMap],
  );
  const actualData = useMemo(() => aggregateActualByCategory(sessions), [sessions]);

  const loading = blocksLoading || sessionsLoading;

  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4 space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="font-medium text-sm">Category variance</h3>
        {!fromProp && (
          <select
            value={preset}
            onChange={(e) => setPreset(e.target.value as RangePreset)}
            aria-label="Chart date range"
            className="text-xs rounded-lg border border-white/10 bg-white/5 px-2 py-1"
          >
            <option value="today">Today</option>
            <option value="week">This week (Mon–Sun)</option>
            <option value="last7">Last 7 days</option>
          </select>
        )}
      </div>

      <p className="text-[11px] text-muted-foreground">
        Planned uses task names; actual uses desktop tracker categories for the selected range.
      </p>

      {loading ? (
        <div className="grid gap-4 md:grid-cols-2">
          <div className="h-[260px] rounded-lg bg-white/5 animate-pulse" />
          <div className="h-[260px] rounded-lg bg-white/5 animate-pulse" />
        </div>
      ) : (
        <div className="grid gap-6 md:grid-cols-2">
          <ChartPanel
            title="Planned hours by task"
            data={plannedData}
            color="#8b5cf6"
            emptyMessage="No planned blocks in range"
          />
          <ChartPanel
            title="Actual hours by tracker category"
            data={actualData}
            color="#0ea5e9"
            emptyMessage="No tracked sessions in range"
          />
        </div>
      )}
    </div>
  );
}

export default CategoryVarianceChart;
