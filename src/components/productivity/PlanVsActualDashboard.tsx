import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  CalendarDays,
  ClipboardList,
  Settings2,
  Target,
  Activity,
  Shield,
} from "lucide-react";
import type { TrackerHealth } from "../../api/behaviorClient";
import {
  fetchDayRollupMirror,
  fetchEnforcerStatusMirror,
  type DayRollupMirror,
  type EnforcerStatusMirror,
} from "../../api/focusMirrors";
import { isFocusEnforcerBridgeAvailable } from "../../lib/enforcerNativeCmd";
import { isFocusDesktopShell } from "../../utils/focusDesktopShell";
import { resolveApiUrl } from "../../utils/resolveBackendUrl";
import { useActualOverlay, useAdherenceRange, usePlannerBlocks } from "../../hooks/usePlanVsActual";
import { CategoryVarianceChart } from "./CategoryVarianceChart";
import { DayRibbon } from "./DayRibbon";
import { FocusRhythmPanel } from "./FocusRhythmPanel";
import { FocusQualityBadge } from "./FocusQualityBadge";
import { WeeklyAdherenceHeatmap } from "./WeeklyAdherenceHeatmap";
import type { FocusRhythmView } from "./planVsActualUtils";
import { fmtDurationMinutes, toDayString } from "./planVsActualUtils";

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
  /** Navigate Focus tabs without Study API messaging */
  onNavigateTab?: (tab: "plan" | "calendar" | "settings") => void;
};

function StatusChip({
  ok,
  warn,
  label,
  title,
}: {
  ok: boolean;
  warn?: boolean;
  label: string;
  title?: string;
}) {
  const tone = ok
    ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-200"
    : warn
      ? "border-amber-500/30 bg-amber-500/10 text-amber-200"
      : "border-white/10 bg-white/5 text-muted-foreground";
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[11px] ${tone}`}
      title={title}
    >
      <span
        className={`h-1.5 w-1.5 rounded-full ${
          ok ? "bg-emerald-400" : warn ? "bg-amber-400" : "bg-white/30"
        }`}
      />
      {label}
    </span>
  );
}

function NextActions({
  onNavigateTab,
  bridgeOk,
}: {
  onNavigateTab?: (tab: "plan" | "calendar" | "settings") => void;
  bridgeOk: boolean;
}) {
  const actions: { tab: "plan" | "calendar" | "settings"; icon: typeof ClipboardList; label: string; hint: string }[] = [
    { tab: "plan", icon: ClipboardList, label: "Open Plan", hint: "Schedule today’s blocks" },
    { tab: "calendar", icon: CalendarDays, label: "Calendar", hint: "See the week at a glance" },
    { tab: "settings", icon: Settings2, label: "Settings", hint: bridgeOk ? "SoftLand & Arm" : "Check enforcer / SoftLand" },
  ];

  return (
    <div className="flex flex-wrap gap-2">
      {actions.map(({ tab, icon: Icon, label, hint }) => (
        <button
          key={tab}
          type="button"
          onClick={() => onNavigateTab?.(tab)}
          className="group flex min-w-[9.5rem] flex-1 items-start gap-2 rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2.5 text-left transition-colors hover:border-white/20 hover:bg-white/[0.06]"
        >
          <Icon size={14} className="mt-0.5 text-primary shrink-0" aria-hidden />
          <span>
            <span className="block text-xs font-medium text-foreground">{label}</span>
            <span className="block text-[10px] text-muted-foreground group-hover:text-muted-foreground/90">
              {hint}
            </span>
          </span>
        </button>
      ))}
    </div>
  );
}

function SummaryStat({
  label,
  value,
  sub,
}: {
  label: string;
  value: string;
  sub?: string;
}) {
  return (
    <div className="rounded-xl border border-white/10 bg-black/15 px-3 py-2.5 min-w-0">
      <p className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</p>
      <p className="mt-0.5 text-lg font-semibold tabular-nums text-foreground">{value}</p>
      {sub ? <p className="text-[10px] text-muted-foreground mt-0.5 truncate">{sub}</p> : null}
    </div>
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
  onNavigateTab,
}: Props) {
  const focusShell = isFocusDesktopShell();
  const bridgeOk = !focusShell || isFocusEnforcerBridgeAvailable();
  const ribbonRef = useRef<HTMLDivElement>(null);

  const {
    data: adherenceDays,
    loading: adherenceLoading,
    error: adherenceError,
  } = useAdherenceRange(adherenceWindow, adherenceEnd ?? selectedDay);
  const rhythmFrom = analyticsFrom ?? selectedDay;
  const rhythmTo = analyticsTo ?? selectedDay;
  const { data: rhythmBlocks, loading: rhythmBlocksLoading } = usePlannerBlocks(rhythmFrom, rhythmTo);
  const { data: rhythmSessions, loading: rhythmSessionsLoading } = useActualOverlay(
    rhythmFrom,
    rhythmTo,
    refreshKey,
  );

  const [trackerHealthLocal, setTrackerHealthLocal] = useState<TrackerHealth | null>(null);
  const [studyApiStale, setStudyApiStale] = useState(false);
  const [rollup, setRollup] = useState<DayRollupMirror | null>(null);
  const [enforcerStatus, setEnforcerStatus] = useState<EnforcerStatusMirror | null>(null);

  const trackerHealth = trackerHealthProp ?? trackerHealthLocal;

  const selectedKey = toDayString(selectedDay);
  const selectedAdherence = useMemo(
    () => adherenceDays.find((d) => d.date === selectedKey) ?? null,
    [adherenceDays, selectedKey],
  );

  const loadFocusMirrors = useCallback(async () => {
    if (!focusShell) return;
    const [r, e] = await Promise.all([fetchDayRollupMirror(), fetchEnforcerStatusMirror()]);
    setRollup(r);
    setEnforcerStatus(e);
  }, [focusShell]);

  const loadStudyHealth = useCallback(async () => {
    if (focusShell) return;
    try {
      const healthRes = await fetch(resolveApiUrl("/health"));
      if (healthRes.ok) {
        const health = (await healthRes.json()) as {
          features?: { behavior_desktop_timeline?: boolean; planner?: boolean };
        };
        const missing =
          health.features &&
          (!health.features.behavior_desktop_timeline || !health.features.planner);
        setStudyApiStale(Boolean(missing));
      }
      if (trackerHealthProp === undefined) {
        const { fetchTrackerHealth } = await import("../../api/behaviorClient");
        const h = await fetchTrackerHealth();
        setTrackerHealthLocal(h);
      }
    } catch {
      if (trackerHealthProp === undefined) setTrackerHealthLocal(null);
      setStudyApiStale(true);
    }
  }, [focusShell, trackerHealthProp]);

  useEffect(() => {
    void loadFocusMirrors();
    void loadStudyHealth();
    if (!focusShell && trackerHealthProp === undefined) {
      const id = setInterval(() => {
        if (typeof document !== "undefined" && document.visibilityState === "hidden") return;
        void loadStudyHealth();
      }, 60_000);
      return () => clearInterval(id);
    }
    if (focusShell) {
      const id = setInterval(() => {
        if (typeof document !== "undefined" && document.visibilityState === "hidden") return;
        void loadFocusMirrors();
      }, 60_000);
      return () => clearInterval(id);
    }
  }, [focusShell, loadFocusMirrors, loadStudyHealth, trackerHealthProp, refreshKey]);

  const handleSelectDay = (d: Date) => {
    onSelectedDayChange?.(d);
    requestAnimationFrame(() => {
      ribbonRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    });
  };

  const dayLabel = selectedDay.toLocaleDateString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
  });

  const enforcerLive = Boolean(
    enforcerStatus?.owns || enforcerStatus?.service_running || enforcerStatus?.pid,
  );
  const softlandOn = Boolean(enforcerStatus?.softland_or_armed);
  const armed = Boolean(enforcerStatus?.armed);
  const productiveFromRollup =
    typeof rollup?.productive_minutes === "number"
      ? rollup.productive_minutes
      : typeof rollup?.productive_seconds === "number"
        ? Math.round(rollup.productive_seconds / 60)
        : null;

  const plannedMin = selectedAdherence?.planned ?? 0;
  const productiveMin =
    selectedAdherence && selectedAdherence.productive > 0
      ? selectedAdherence.productive
      : productiveFromRollup ?? selectedAdherence?.actual ?? 0;
  const adherencePct = selectedAdherence?.pct;
  const hasPlan = Boolean(selectedAdherence && !selectedAdherence.noPlan && plannedMin > 0);
  const hasAnyAdherenceSignal = adherenceDays.some((d) => !d.noPlan || (d.actual ?? 0) > 0);
  const offlineFocus = focusShell && !bridgeOk;

  const emptyStory = offlineFocus
    ? "Enforcer isn’t reachable from this window yet. Open Focus from the tray so plan and tracker data can load — SoftLand and Arm still live in Settings."
    : !hasPlan && !hasAnyAdherenceSignal
      ? "No plan blocks for this window yet. Schedule focus time, then come back to see how the day went."
      : !hasPlan
        ? "This day has no planned blocks — pick another day on the strip, or add blocks in Plan."
        : null;

  return (
    <div className="space-y-5">
      {/* Hero — one purpose */}
      <header className="space-y-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0 space-y-1">
            <h2 className="flex items-center gap-2 text-base font-semibold tracking-tight">
              <Target size={18} className="text-primary shrink-0" aria-hidden />
              Focus Analytics
            </h2>
            <p className="text-xs text-muted-foreground max-w-xl">
              How today and this week went versus your plan — on-plan focus, drift, and rhythm.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-1.5 justify-end">
            {focusShell ? (
              <>
                <StatusChip
                  ok={bridgeOk && enforcerLive}
                  warn={bridgeOk && !enforcerLive}
                  label={
                    !bridgeOk
                      ? "Enforcer offline"
                      : enforcerLive
                        ? "Enforcer live"
                        : "Enforcer idle"
                  }
                  title="Native enforcer owns kills and SoftLand state"
                />
                <StatusChip
                  ok={softlandOn}
                  warn={!softlandOn && bridgeOk}
                  label={softlandOn ? "SoftLand on" : "SoftLand off"}
                  title="SoftLand ON ≠ Arm"
                />
                <StatusChip
                  ok={armed}
                  warn={!armed && softlandOn}
                  label={armed ? "Armed" : "Not armed"}
                  title="Hard-block arm is separate from SoftLand"
                />
              </>
            ) : (
              <StatusChip
                ok={trackerHealth?.status === "running"}
                warn={trackerHealth?.status === "stale"}
                label={
                  trackerHealth?.status === "running"
                    ? "Tracker running"
                    : trackerHealth?.status === "stale"
                      ? "Tracker stale"
                      : "No tracker data"
                }
              />
            )}
          </div>
        </div>

        {/* Study-only stale API hint — never shown in Focus */}
        {!focusShell && import.meta.env.DEV && studyApiStale ? (
          <p className="text-[11px] text-amber-200/80">
            Dev: Study API missing planner/tracker features — restart{" "}
            <code className="text-[10px]">run.bat</code>.
          </p>
        ) : null}

        {focusShell && adherenceError && bridgeOk ? (
          <p className="text-[11px] text-muted-foreground">
            Couldn’t refresh adherence ({adherenceError}). Showing what we have from mirrors and plan.
          </p>
        ) : null}
      </header>

      {/* Selected-day summary */}
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <SummaryStat label="Selected" value={dayLabel} sub={analyticsView === "day" ? "Day view" : `${analyticsView} range`} />
        <SummaryStat
          label="Planned"
          value={hasPlan ? fmtDurationMinutes(plannedMin) : "—"}
          sub={hasPlan ? `${selectedAdherence?.blockCount ?? 0} blocks` : "No blocks"}
        />
        <SummaryStat
          label="Productive"
          value={productiveMin > 0 ? fmtDurationMinutes(productiveMin) : "—"}
          sub={
            productiveFromRollup != null && focusShell
              ? "From day rollup / overlay"
              : trackerHealth?.status === "running"
                ? "Tracker live"
                : "Tracked focus"
          }
        />
        <SummaryStat
          label="On-plan"
          value={adherencePct != null ? `${Math.round(adherencePct)}%` : "—"}
          sub={adherencePct != null ? "Adherence" : "Needs plan + track"}
        />
      </div>

      {emptyStory ? (
        <div className="rounded-xl border border-white/10 bg-gradient-to-br from-white/[0.04] to-transparent px-4 py-4 space-y-3">
          <div className="flex items-start gap-2.5">
            {offlineFocus ? (
              <Shield size={16} className="mt-0.5 text-amber-300/90 shrink-0" aria-hidden />
            ) : (
              <Activity size={16} className="mt-0.5 text-primary shrink-0" aria-hidden />
            )}
            <div className="space-y-1 min-w-0">
              <p className="text-sm font-medium text-foreground">
                {offlineFocus ? "Waiting on Focus enforcer" : "Start a plan to fill this view"}
              </p>
              <p className="text-xs text-muted-foreground leading-relaxed">{emptyStory}</p>
            </div>
          </div>
          {onNavigateTab ? <NextActions onNavigateTab={onNavigateTab} bridgeOk={bridgeOk} /> : null}
        </div>
      ) : null}

      <WeeklyAdherenceHeatmap
        days={adherenceDays}
        selectedDay={selectedDay}
        onSelectDay={handleSelectDay}
        loading={adherenceLoading}
        windowLabel={adherenceWindow > 7 ? "Adherence" : "Weekly adherence"}
        emptyHint={
          focusShell
            ? offlineFocus
              ? "Adherence loads when the Focus enforcer bridge is available."
              : "Gray days = no plan yet. Add blocks in Plan to light up the strip."
            : undefined
        }
      />

      <FocusRhythmPanel
        blocks={rhythmBlocks}
        sessions={rhythmSessions}
        from={rhythmFrom}
        to={rhythmTo}
        view={analyticsView}
        loading={rhythmBlocksLoading || rhythmSessionsLoading}
        focusShell={focusShell}
        offline={offlineFocus}
        onOpenPlan={onNavigateTab ? () => onNavigateTab("plan") : undefined}
      />

      <FocusQualityBadge day={toDayString(selectedDay)} refreshKey={refreshKey} />

      <DayRibbon
        ref={ribbonRef}
        day={selectedDay}
        refreshKey={refreshKey}
        focusShell={focusShell}
        offline={offlineFocus}
        onOpenPlan={onNavigateTab ? () => onNavigateTab("plan") : undefined}
        blocks={
          analyticsView === "day" && toDayString(rhythmFrom) === selectedKey
            ? rhythmBlocks
            : undefined
        }
        overlay={
          analyticsView === "day" && toDayString(rhythmFrom) === selectedKey
            ? rhythmSessions
            : undefined
        }
        loading={
          analyticsView === "day" && toDayString(rhythmFrom) === selectedKey
            ? rhythmBlocksLoading || rhythmSessionsLoading
            : undefined
        }
      />

      {!focusShell && trackerHealth?.status === "no_data" ? (
        <p className="text-xs text-muted-foreground">
          No tracked activity yet — start the desktop tracker, then Sync tracker.
        </p>
      ) : null}

      <CategoryVarianceChart
        from={rhythmFrom}
        to={rhythmTo}
        focusShell={focusShell}
        offline={offlineFocus}
        blocks={rhythmBlocks}
        sessions={rhythmSessions}
        loading={rhythmBlocksLoading || rhythmSessionsLoading}
      />
    </div>
  );
}

export default PlanVsActualDashboard;
