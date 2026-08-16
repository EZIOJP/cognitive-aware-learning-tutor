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
  endOfDay,
  endOfWeekSunday,
  startOfDay,
  startOfWeekMonday,
} from "./planVsActualUtils";

type RangePreset = "day" | "week" | "month" | "last7";

type Props = {
  from?: Date;
  to?: Date;
  baseDate?: Date;
  defaultPreset?: RangePreset;
};

const STACK_COLORS = [
  "#8b5cf6",
  "#0ea5e9",
  "#34d399",
  "#fbbf24",
  "#f472b6",
  "#94a3b8",
  "#fb923c",
  "#2dd4bf",
];

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
            label={{
              value: "Hours",
              angle: -90,
              position: "insideLeft",
              fill: "rgba(255,255,255,0.4)",
              fontSize: 10,
            }}
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

function StackedSummary({
  title,
  data,
  emptyMessage,
}: {
  title: string;
  data: { name: string; hours: number }[];
  emptyMessage: string;
}) {
  const total = data.reduce((s, d) => s + d.hours, 0);
  if (data.length === 0 || total <= 0) {
    return (
      <div className="space-y-1.5">
        <h4 className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
          {title}
        </h4>
        <p className="text-xs text-muted-foreground">{emptyMessage}</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <h4 className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
        {title}
      </h4>
      <div
        className="flex h-3 w-full overflow-hidden rounded-full bg-white/5"
        role="img"
        aria-label={`${title}: ${total.toFixed(1)} hours`}
      >
        {data.map((d, i) => (
          <div
            key={d.name}
            title={`${d.name}: ${d.hours}h`}
            style={{
              width: `${(d.hours / total) * 100}%`,
              backgroundColor: STACK_COLORS[i % STACK_COLORS.length],
            }}
            className="h-full min-w-[2px]"
          />
        ))}
      </div>
      <div className="flex flex-wrap gap-x-3 gap-y-1">
        {data.slice(0, 6).map((d, i) => (
          <span key={d.name} className="inline-flex items-center gap-1.5 text-[10px] text-muted-foreground">
            <span
              className="inline-block h-2 w-2 rounded-sm"
              style={{ backgroundColor: STACK_COLORS[i % STACK_COLORS.length] }}
            />
            <span className="truncate max-w-[8rem]">{d.name}</span>
            <span className="tabular-nums text-foreground/80">{d.hours}h</span>
          </span>
        ))}
        {data.length > 6 ? (
          <span className="text-[10px] text-muted-foreground">+{data.length - 6} more</span>
        ) : null}
      </div>
    </div>
  );
}

export function CategoryVarianceChart({ from: fromProp, to: toProp, baseDate, defaultPreset = "day" }: Props) {
  const [preset, setPreset] = useState<RangePreset>(defaultPreset);
  const [taskMap, setTaskMap] = useState<Map<number, string>>(new Map());
  const [showFull, setShowFull] = useState(false);

  const { from, to } = useMemo(() => {
    if (fromProp && toProp) return { from: fromProp, to: toProp };
    const anchor = baseDate ? new Date(baseDate) : new Date();
    if (preset === "day") {
      return { from: startOfDay(anchor), to: endOfDay(anchor) };
    }
    if (preset === "week") {
      return { from: startOfWeekMonday(anchor), to: endOfWeekSunday(anchor) };
    }
    if (preset === "month") {
      const start = new Date(anchor.getFullYear(), anchor.getMonth(), 1);
      const end = new Date(anchor.getFullYear(), anchor.getMonth() + 1, 0);
      return { from: startOfDay(start), to: endOfDay(end) };
    }
    const end = endOfDay(anchor);
    const start = new Date(anchor);
    start.setDate(start.getDate() - 6);
    return { from: startOfDay(start), to: end };
  }, [fromProp, toProp, baseDate?.getTime(), preset]);

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
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
          Category variance
        </h3>
        {!fromProp && (
          <select
            value={preset}
            onChange={(e) => setPreset(e.target.value as RangePreset)}
            aria-label="Chart date range"
            className="text-xs rounded-lg border border-white/10 bg-white/5 px-2 py-1"
          >
            <option value="day">Selected day</option>
            <option value="week">Selected week (Mon–Sun)</option>
            <option value="month">Selected month</option>
            <option value="last7">7 days ending selected day</option>
          </select>
        )}
      </div>

      {loading ? (
        <div className="h-10 rounded-full bg-white/5 animate-pulse" />
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          <StackedSummary
            title="Planned by task"
            data={plannedData}
            emptyMessage="No planned blocks in range"
          />
          <StackedSummary
            title="Actual by category"
            data={actualData}
            emptyMessage="No tracked sessions in range"
          />
        </div>
      )}

      <button
        type="button"
        onClick={() => setShowFull((v) => !v)}
        className="text-xs text-violet-300/90 hover:text-violet-200 underline-offset-2 hover:underline"
      >
        {showFull ? "Hide full breakdown" : "See full breakdown"}
      </button>

      {showFull && !loading ? (
        <div className="grid gap-6 md:grid-cols-2 pt-1 border-t border-white/10">
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
      ) : null}
    </div>
  );
}

export default CategoryVarianceChart;
