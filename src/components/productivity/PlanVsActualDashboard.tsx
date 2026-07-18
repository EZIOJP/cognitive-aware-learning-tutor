import { useCallback, useEffect, useRef, useState } from "react";
import { AlertCircle, Target } from "lucide-react";
import { fetchTrackerHealth } from "../../api/behaviorClient";
import type { TrackerHealth } from "../../api/behaviorClient";
import { resolveApiUrl } from "../../utils/resolveBackendUrl";
import { useAdherenceRange } from "../../hooks/usePlanVsActual";
import { AdherenceStreak } from "./AdherenceStreak";
import { CategoryVarianceChart } from "./CategoryVarianceChart";
import { DayRibbon } from "./DayRibbon";
import { WeeklyAdherenceHeatmap } from "./WeeklyAdherenceHeatmap";

type Props = {
  selectedDay: Date;
  onSelectedDayChange?: (d: Date) => void;
  /** Bump after Sync tracker / planner refresh to reload day ribbon */
  refreshKey?: number;
  /** Parent tracker health — avoids duplicate fetch when provided */
  trackerHealth?: TrackerHealth | null;
  /** Heatmap window length (7 week / month length) */
  adherenceDays?: number;
  /** Inclusive end of adherence window */
  adherenceEnd?: Date;
  variancePreset?: "day" | "week" | "month" | "last7";
};

function TrackerDot({ health }: { health: TrackerHealth | null }) {
  const status = health?.status ?? "no_data";
  const color =
    status === "running"
      ? "bg-emerald-400"
      : status === "stale"
        ? "bg-yellow-400"
        : "bg-gray-500";
  const label =
    status === "running"
      ? "Tracker running"
      : status === "stale"
        ? "Tracker stale"
        : "No tracker data";

  return (
    <span className="flex items-center gap-1.5 text-[11px] text-muted-foreground" title={label}>
      <span className={`w-2 h-2 rounded-full ${color}`} />
      {label}
    </span>
  );
}

export function PlanVsActualDashboard({
  selectedDay,
  onSelectedDayChange,
  refreshKey = 0,
  trackerHealth: trackerHealthProp,
  adherenceDays: adherenceWindow = 7,
  adherenceEnd,
  variancePreset = "week",
}: Props) {
  const ribbonRef = useRef<HTMLDivElement>(null);
  const { data: adherenceDays, loading: adherenceLoading } = useAdherenceRange(
    adherenceWindow,
    adherenceEnd ?? selectedDay,
  );
  const [trackerHealthLocal, setTrackerHealthLocal] = useState<TrackerHealth | null>(null);
  const [apiStale, setApiStale] = useState(false);

  const trackerHealth = trackerHealthProp ?? trackerHealthLocal;

  const loadHealth = useCallback(async () => {
    try {
      const healthRes = await fetch(resolveApiUrl("/health"));
      if (healthRes.ok) {
        const health = (await healthRes.json()) as {
          features?: { behavior_desktop_timeline?: boolean; planner?: boolean };
        };
        const missing =
          health.features &&
          (!health.features.behavior_desktop_timeline || !health.features.planner);
        setApiStale(Boolean(missing));
      }
      if (trackerHealthProp === undefined) {
        const h = await fetchTrackerHealth();
        setTrackerHealthLocal(h);
      }
    } catch {
      if (trackerHealthProp === undefined) {
        setTrackerHealthLocal(null);
      }
      setApiStale(true);
    }
  }, [trackerHealthProp]);

  useEffect(() => {
    if (trackerHealthProp !== undefined) {
      // Parent already polls tracker health — only check API feature flags once.
      void loadHealth();
      return;
    }
    void loadHealth();
    const id = setInterval(() => {
      if (typeof document !== "undefined" && document.visibilityState === "hidden") return;
      void loadHealth();
    }, 60_000);
    return () => clearInterval(id);
  }, [loadHealth, trackerHealthProp]);

  const handleSelectDay = (d: Date) => {
    onSelectedDayChange?.(d);
    requestAnimationFrame(() => {
      ribbonRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    });
  };

  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-6 space-y-4">
      {apiStale && (
        <div className="flex items-start gap-2 p-3 rounded-xl border border-amber-500/30 bg-amber-500/10 text-amber-200 text-sm">
          <AlertCircle size={16} className="shrink-0 mt-0.5" />
          <p>
            API server is running an old build (missing planner/tracker routes). Close the{" "}
            <strong>API</strong> terminal window and run <code className="text-xs bg-black/30 px-1 rounded">run.bat</code>{" "}
            again, then refresh this page.
          </p>
        </div>
      )}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="font-semibold flex items-center gap-2 text-sm">
          <Target size={16} className="text-violet-400" />
          Plan vs actual
        </h2>
        <TrackerDot health={trackerHealth} />
      </div>

      <div className="flex flex-col md:flex-row gap-4">
        <WeeklyAdherenceHeatmap
          days={adherenceDays}
          selectedDay={selectedDay}
          onSelectDay={handleSelectDay}
          loading={adherenceLoading}
        />
        <div className="shrink-0 md:w-44">
          <AdherenceStreak days={adherenceDays} loading={adherenceLoading} />
        </div>
      </div>

      <DayRibbon ref={ribbonRef} day={selectedDay} refreshKey={refreshKey} />

      {trackerHealth?.status === "no_data" && (
        <p className="text-xs text-muted-foreground -mt-2">
          No tracked activity yet — run{" "}
          <code className="bg-black/30 px-1 rounded text-[10px] font-mono">
            scripts\desktop_tracker\run_desktop_tracker_headless.bat
          </code>{" "}
          then use Sync tracker above.
        </p>
      )}

      <details open className="group">
        <summary className="cursor-pointer text-sm font-medium text-muted-foreground hover:text-foreground list-none flex items-center gap-2">
          <span className="text-violet-400">▸</span>
          Category variance (planned vs actual)
        </summary>
        <div className="mt-3">
          <CategoryVarianceChart
            key={variancePreset}
            baseDate={selectedDay}
            defaultPreset={variancePreset}
          />
        </div>
      </details>
    </div>
  );
}

export default PlanVsActualDashboard;
