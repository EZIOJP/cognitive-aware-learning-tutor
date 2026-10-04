import {
  forwardRef,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type MouseEvent as ReactMouseEvent,
} from "react";
import { blockColor } from "../../api/plannerClient";
import type { PlannerBlock, ActualSession } from "../../api/plannerClient";
import { useActualOverlay, usePlannerBlocks } from "../../hooks/usePlanVsActual";
import { ActivityDetailPanel, type EventAnchorRect } from "./ActivityDetailPanel";
import {
  actualOverlapsPlanned,
  clipSessionsAgainstSleep,
  computeAxisWindow,
  endOfDay,
  fmtDurationMinutes,
  isSleepSession,
  mergeAdjacentIntervals,
  mergedIntervalLabel,
  minutesClippedToDay,
  parseApiDate,
  PRODUCTIVE_THRESHOLD,
  startOfDay,
  toDayString,
  toSegmentStyle,
  type MergedInterval,
} from "./planVsActualUtils";

/** Wider gap for ribbon paint — fewer DOM/SVG nodes; detail panel still uses merged children. */
const RIBBON_MERGE_GAP_SEC = 300;

type Props = {
  day: Date;
  refreshKey?: number;
  focusShell?: boolean;
  offline?: boolean;
  onOpenPlan?: () => void;
  /** Shared fetch from PlanVsActualDashboard — skips duplicate hooks when set. */
  blocks?: PlannerBlock[];
  overlay?: ActualSession[];
  loading?: boolean;
  error?: string | null;
};

type FocusState =
  | { kind: "actual"; interval: MergedInterval; onPlan: boolean; productive: boolean; sleep?: boolean }
  | { kind: "planned"; block: PlannerBlock };

type PaintedActual = {
  key: string;
  interval: MergedInterval;
  leftPct: number;
  widthPct: number;
  onPlan: boolean;
  productive: boolean;
  sleep: boolean;
  fill: string;
  title: string;
};

function overlayToMergeable(s: ActualSession) {
  if (!s.start_time || !s.end_time) return null;
  const start = parseApiDate(s.start_time).getTime();
  const end = parseApiDate(s.end_time).getTime();
  if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start) return null;
  return {
    session_id: s.session_id,
    start_time: s.start_time,
    end_time: s.end_time,
    app_name: s.app_name ?? null,
    category: s.category ?? null,
    window_title: s.window_title ?? null,
    site: s.site ?? null,
    source: s.source ?? null,
    productivity_score: s.productivity_score ?? null,
    duration_seconds: Math.max(1, Math.round((end - start) / 1000)),
  };
}

function hourLabels(axisStart: number, axisEnd: number): number[] {
  const startHour = Math.floor(axisStart / 60);
  const endHour = Math.ceil(axisEnd / 60);
  const labels: number[] = [];
  for (let h = startHour; h <= endHour; h += 3) {
    if (h >= 0 && h <= 24) labels.push(h);
  }
  return labels;
}

function formatHour(h: number): string {
  if (h === 0 || h === 24) return "12am";
  if (h === 12) return "12pm";
  if (h < 12) return `${h}am`;
  return `${h - 12}pm`;
}

export const DayRibbon = forwardRef<HTMLDivElement, Props>(function DayRibbon(
  {
    day,
    refreshKey = 0,
    focusShell = false,
    offline = false,
    onOpenPlan,
    blocks: blocksProp,
    overlay: overlayProp,
    loading: loadingProp,
    error: errorProp,
  },
  ref,
) {
  const dayStr = toDayString(day);
  const from = startOfDay(day);
  const to = endOfDay(day);
  const wrapRef = useRef<HTMLDivElement>(null);
  const actualTrackRef = useRef<HTMLDivElement>(null);
  const [focus, setFocus] = useState<FocusState | null>(null);
  const [anchor, setAnchor] = useState<EventAnchorRect | null>(null);

  const useShared = blocksProp != null && overlayProp != null;
  const fetchedBlocks = usePlannerBlocks(from, to, !useShared);
  const fetchedOverlay = useActualOverlay(from, to, refreshKey, !useShared);

  const blocks = useShared ? blocksProp! : fetchedBlocks.data;
  const overlay = useShared ? overlayProp! : fetchedOverlay.data;
  const blocksError = useShared ? errorProp ?? null : fetchedBlocks.error;
  const overlayError = useShared ? errorProp ?? null : fetchedOverlay.error;
  // Cold skeleton only when we have nothing to paint yet.
  const loading =
    (useShared ? Boolean(loadingProp) : fetchedBlocks.loading || fetchedOverlay.loading) &&
    blocks.length === 0 &&
    overlay.length === 0;

  const { intervals, sleepIntervals } = useMemo(() => {
    const sleepSessions = overlay.filter(isSleepSession);
    const restSessions = overlay.filter((s) => !isSleepSession(s));
    const clipped = clipSessionsAgainstSleep(restSessions, sleepSessions);
    const toRows = (rows: ActualSession[]) =>
      rows.map(overlayToMergeable).filter((row): row is NonNullable<typeof row> => row != null);
    return {
      intervals: mergeAdjacentIntervals(toRows(clipped), RIBBON_MERGE_GAP_SEC),
      sleepIntervals: mergeAdjacentIntervals(toRows(sleepSessions), RIBBON_MERGE_GAP_SEC),
    };
  }, [overlay]);

  const { axisStart, axisEnd } = useMemo(
    () => computeAxisWindow(blocks, [...intervals, ...sleepIntervals], day),
    [blocks, intervals, sleepIntervals, day],
  );
  const hours = useMemo(() => hourLabels(axisStart, axisEnd), [axisStart, axisEnd]);

  const paintedActual = useMemo((): PaintedActual[] => {
    const out: PaintedActual[] = [];
    const push = (iv: MergedInterval, sleep: boolean, idx: number) => {
      const clipped = minutesClippedToDay(iv.start_time, iv.end_time, day);
      if (!clipped) return;
      const style = toSegmentStyle(clipped.startMin, clipped.endMin, axisStart, axisEnd);
      const leftPct = Number.parseFloat(style.left);
      const widthPct = Number.parseFloat(style.width);
      if (!Number.isFinite(leftPct) || !Number.isFinite(widthPct) || widthPct <= 0) return;
      const onPlan = sleep ? false : actualOverlapsPlanned(clipped.startMin, clipped.endMin, blocks);
      const productive = (iv.productivity_score ?? 0) >= PRODUCTIVE_THRESHOLD;
      const fill = sleep
        ? "#6366f1"
        : onPlan
          ? productive
            ? "#10b981"
            : "#f43f5e"
          : "#f59e0b";
      out.push({
        key: `${sleep ? "sleep" : "act"}-${iv.start_time}-${idx}`,
        interval: iv,
        leftPct,
        widthPct,
        onPlan,
        productive,
        sleep,
        fill,
        title: mergedIntervalLabel(iv),
      });
    };
    sleepIntervals.forEach((iv, i) => push(iv, true, i));
    intervals.forEach((iv, i) => push(iv, false, i));
    return out;
  }, [intervals, sleepIntervals, blocks, day, axisStart, axisEnd]);

  const dayLabel = day.toLocaleDateString(undefined, {
    weekday: "long",
    month: "short",
    day: "numeric",
  });

  const openAt = useCallback((el: HTMLElement, next: FocusState) => {
    const wrap = wrapRef.current;
    if (!wrap) return;
    const wrapR = wrap.getBoundingClientRect();
    const evR = el.getBoundingClientRect();
    setAnchor({
      top: evR.top - wrapR.top + wrap.scrollTop,
      left: evR.left - wrapR.left + wrap.scrollLeft,
      width: Math.max(8, evR.width),
      height: evR.height,
    });
    setFocus(next);
  }, []);

  const onActualSvgClick = useCallback(
    (e: ReactMouseEvent<SVGSVGElement>) => {
      const track = actualTrackRef.current;
      if (!track || paintedActual.length === 0) return;
      const r = track.getBoundingClientRect();
      if (r.width < 1) return;
      const pct = ((e.clientX - r.left) / r.width) * 100;
      // Prefer shorter / topmost segments covering this x (last painted wins).
      let hit: PaintedActual | null = null;
      for (const seg of paintedActual) {
        if (pct >= seg.leftPct && pct <= seg.leftPct + seg.widthPct) hit = seg;
      }
      if (!hit) return;
      const anchorEl = track;
      openAt(anchorEl, {
        kind: "actual",
        interval: hit.interval,
        onPlan: hit.onPlan,
        productive: hit.productive,
        sleep: hit.sleep,
      });
      // Narrow popup to the clicked slice.
      const wrap = wrapRef.current;
      if (wrap) {
        const wrapR = wrap.getBoundingClientRect();
        const left = r.left - wrapR.left + wrap.scrollLeft + (hit.leftPct / 100) * r.width;
        const width = Math.max(8, (hit.widthPct / 100) * r.width);
        setAnchor({
          top: r.top - wrapR.top + wrap.scrollTop,
          left,
          width,
          height: r.height,
        });
      }
    },
    [paintedActual, openAt],
  );

  useEffect(() => {
    setFocus(null);
    setAnchor(null);
  }, [dayStr]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setFocus(null);
        setAnchor(null);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const containerW = wrapRef.current?.clientWidth ?? 600;
  const containerH = wrapRef.current?.clientHeight ?? 200;

  const rawError = blocksError || overlayError;
  const friendlyError =
    !rawError
      ? null
      : rawError === "enforcer_unreachable" || offline
        ? focusShell
          ? "Enforcer unreachable — open Focus from the tray to load plan vs actual."
          : rawError
        : rawError;

  return (
    <div ref={ref} className="scroll-mt-4">
      <div
        ref={wrapRef}
        className={`relative min-w-0 rounded-xl border border-white/10 bg-white/[0.03] p-4 space-y-3 ${
          focus ? "overflow-visible" : "overflow-hidden"
        }`}
        onClickCapture={(e) => {
          if (!focus) return;
          const t = e.target as HTMLElement;
          if (t.closest('[role="dialog"]') || t.closest(".ribbon-segment") || t.closest("[data-ribbon-actual]"))
            return;
          setFocus(null);
          setAnchor(null);
        }}
      >
        <div className="flex items-center justify-between gap-2">
          <div>
            <h3 className="font-medium text-sm">Day ribbon — {dayLabel}</h3>
            <p className="text-[10px] text-muted-foreground mt-0.5">
              Planned vs actual on one timeline. Click a segment for details.
            </p>
          </div>
          {friendlyError ? (
            <span className="text-[11px] text-muted-foreground text-right max-w-[14rem]">{friendlyError}</span>
          ) : null}
        </div>

        <div className="relative min-w-0">
          <div className="relative h-4 mb-1">
            {hours.map((h, i) => {
              const pct = ((h * 60 - axisStart) / Math.max(1, axisEnd - axisStart)) * 100;
              const clamped = Math.min(100, Math.max(0, pct));
              const isFirst = i === 0 || clamped <= 0.5;
              const isLast = i === hours.length - 1 || clamped >= 99.5;
              const alignClass = isFirst
                ? "translate-x-0"
                : isLast
                  ? "-translate-x-full"
                  : "-translate-x-1/2";
              return (
                <span
                  key={h}
                  className={`absolute top-0 text-[10px] text-muted-foreground tabular-nums whitespace-nowrap ${alignClass}`}
                  style={{ left: `${clamped}%` }}
                >
                  {formatHour(h)}
                </span>
              );
            })}
          </div>

          {loading ? (
            <div className="space-y-2">
              <div className="h-8 rounded-lg bg-white/5 animate-pulse" />
              <div className="h-8 rounded-lg bg-white/5 animate-pulse" />
            </div>
          ) : (
            <div className="space-y-2">
              <div>
                <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1">Planned</div>
                <div className="relative h-8 rounded-lg bg-white/5 overflow-hidden">
                  {blocks.length === 0 && (
                    <span className="absolute inset-0 flex items-center justify-center gap-2 text-[11px] text-muted-foreground">
                      {offline ? "Plan unavailable offline" : "No planned blocks"}
                      {!offline && onOpenPlan ? (
                        <button
                          type="button"
                          onClick={onOpenPlan}
                          className="text-primary hover:underline underline-offset-2"
                        >
                          Open Plan
                        </button>
                      ) : null}
                    </span>
                  )}
                  {blocks.map((b) => {
                    if (!b.start_at || !b.end_at) return null;
                    const clipped = minutesClippedToDay(b.start_at, b.end_at, day);
                    if (!clipped) return null;
                    const style = toSegmentStyle(clipped.startMin, clipped.endMin, axisStart, axisEnd);
                    const color = blockColor(b.category, b.color);
                    return (
                      <button
                        key={b.id}
                        type="button"
                        className="ribbon-segment absolute top-0 bottom-0 opacity-90 rounded-sm cursor-pointer hover:brightness-110 focus:outline-none focus:ring-1 focus:ring-primary/50"
                        style={{ ...style, backgroundColor: color }}
                        title={`${b.title} · ${fmtDurationMinutes(b.planned_minutes)} · ${b.category}`}
                        onClick={(e) => openAt(e.currentTarget, { kind: "planned", block: b })}
                      />
                    );
                  })}
                </div>
              </div>

              <div>
                <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1">Actual</div>
                <div
                  ref={actualTrackRef}
                  data-ribbon-actual="1"
                  className="relative h-8 rounded-lg bg-white/5 overflow-hidden"
                >
                  {paintedActual.length === 0 && (
                    <span className="absolute inset-0 flex items-center justify-center text-[11px] text-muted-foreground">
                      {offline
                        ? "Tracking loads with the enforcer"
                        : focusShell
                          ? "No tracked activity yet"
                          : "No tracked activity"}
                    </span>
                  )}
                  {paintedActual.length > 0 ? (
                    <svg
                      className="absolute inset-0 h-full w-full cursor-pointer"
                      viewBox="0 0 1000 32"
                      preserveAspectRatio="none"
                      role="img"
                      aria-label="Actual activity ribbon"
                      onClick={onActualSvgClick}
                    >
                      {paintedActual.map((seg) => (
                        <rect
                          key={seg.key}
                          x={(seg.leftPct / 100) * 1000}
                          y={2}
                          width={Math.max(1.5, (seg.widthPct / 100) * 1000)}
                          height={28}
                          rx={2}
                          fill={seg.fill}
                          opacity={0.88}
                        >
                          <title>{seg.title}</title>
                        </rect>
                      ))}
                    </svg>
                  ) : null}
                </div>
              </div>
            </div>
          )}

          <div className="flex flex-wrap gap-4 mt-2 text-[10px] text-muted-foreground">
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-sm bg-emerald-500" /> On-plan focus
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-sm bg-rose-500" /> Distraction during plan
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-sm bg-amber-500" /> Drift (off plan)
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-sm bg-indigo-500" /> Sleep
            </span>
          </div>
        </div>

        {focus && anchor && focus.kind === "actual" && (
          <ActivityDetailPanel
            popup
            anchor={anchor}
            containerWidth={containerW}
            containerHeight={containerH}
            title={mergedIntervalLabel(focus.interval)}
            start={parseApiDate(focus.interval.start_time)}
            end={parseApiDate(focus.interval.end_time)}
            items={[focus.interval]}
            totalSeconds={focus.interval.duration_seconds}
            planContext={
              focus.sleep
                ? "drift"
                : focus.onPlan
                  ? focus.productive
                    ? "focus"
                    : "distraction"
                  : "drift"
            }
            onClose={() => {
              setFocus(null);
              setAnchor(null);
            }}
          />
        )}

        {focus && anchor && focus.kind === "planned" && (
          <ActivityDetailPanel
            popup
            anchor={anchor}
            containerWidth={containerW}
            containerHeight={containerH}
            title={focus.block.title}
            start={parseApiDate(focus.block.start_at)}
            end={parseApiDate(focus.block.end_at)}
            plannedBlock={{
              title: focus.block.title,
              category: focus.block.category,
              minutes: focus.block.planned_minutes,
            }}
            onClose={() => {
              setFocus(null);
              setAnchor(null);
            }}
          />
        )}
      </div>
    </div>
  );
});

export default DayRibbon;
