import { useCallback, useEffect, useRef, useState } from "react";
import { Target } from "lucide-react";
import { fetchTrackerHealth } from "../../api/behaviorClient";
import type { TrackerHealth } from "../../api/behaviorClient";
import { resolveApiUrl } from "../../utils/resolveBackendUrl";
import { useActualOverlay, useAdherenceRange, usePlannerBlocks } from "../../hooks/usePlanVsActual";
import { CategoryVarianceChart } from "./CategoryVarianceChart";
import { DayRibbon } from "./DayRibbon";
import { FocusRhythmPanel } from "./FocusRhythmPanel";
import { FocusQualityBadge } from "./FocusQualityBadge";
import { WeeklyAdherenceHeatmap } from "./WeeklyAdherenceHeatmap";
import type { FocusRhythmView } from "./planVsActualUtils";
import { toDayString } from "./planVsActualUtils";

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
  /** Calendar range used for focus rhythm and existing category variance. */
  analyticsFrom?: Date;
  analyticsTo?: Date;
  analyticsView?: FocusRhythmView;
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
  analyticsFrom,
  analyticsTo,
  analyticsView = "day",
}: Props) {
  const ribbonRef = useRef<HTMLDivElement>(null);
  const { data: adherenceDays, loading: adherenceLoading } = useAdherenceRange(
    adherenceWindow,
    adherenceEnd ?? selectedDay,
  );
  const rhythmFrom = analyticsFrom ?? selectedDay;
  const rhythmTo = analyticsTo ?? selectedDay;
  const { data: rhythmBlocks, loading: rhythmBlocksLoading } = usePlannerBlocks(rhythmFrom, rhythmTo);
  const { data: rhythmSessions, loading: rhythmSessionsLoading } = useActualOverlay(
    rhythmFrom,
    rhythmTo,
    refreshKey,
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
    <div className="space-y-5">
      {import.meta.env.DEV && apiStale && (
        <p className="text-[11px] text-amber-200/80">
          Dev: API missing planner/tracker features — restart <code className="text-[10px]">run.bat</code>.
        </p>
      )}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="font-semibold flex items-center gap-2 text-sm">
          <Target size={16} className="text-violet-400" />
          Plan vs actual
        </h2>
        <TrackerDot health={trackerHealth} />
      </div>

      <WeeklyAdherenceHeatmap
        days={adherenceDays}
        selectedDay={selectedDay}
        onSelectDay={handleSelectDay}
        loading={adherenceLoading}
        windowLabel={adherenceWindow > 7 ? "Adherence" : "Weekly adherence"}
      />

      <FocusRhythmPanel
        blocks={rhythmBlocks}
        sessions={rhythmSessions}
        from={rhythmFrom}
        to={rhythmTo}
        view={analyticsView}
        loading={rhythmBlocksLoading || rhythmSessionsLoading}
      />

      <FocusQualityBadge day={toDayString(selectedDay)} refreshKey={refreshKey} />

      <DayRibbon ref={ribbonRef} day={selectedDay} refreshKey={refreshKey} />

      {trackerHealth?.status === "no_data" && (
        <p className="text-xs text-muted-foreground">
          No tracked activity yet — start the desktop tracker, then Sync tracker.
        </p>
      )}

      <CategoryVarianceChart
        from={rhythmFrom}
        to={rhythmTo}
      />
    </div>
  );
}

export default PlanVsActualDashboard;
