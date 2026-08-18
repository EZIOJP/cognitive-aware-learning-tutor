import { forwardRef, useCallback, useEffect, useMemo, useRef, useState } from "react";
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

type Props = {
  day: Date;
  refreshKey?: number;
};

type FocusState =
  | { kind: "actual"; interval: MergedInterval; onPlan: boolean; productive: boolean; sleep?: boolean }
  | { kind: "planned"; block: PlannerBlock };

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

export const DayRibbon = forwardRef<HTMLDivElement, Props>(function DayRibbon({ day, refreshKey = 0 }, ref) {
  const dayStr = toDayString(day);
  const from = startOfDay(day);
  const to = endOfDay(day);
  const wrapRef = useRef<HTMLDivElement>(null);
  const [focus, setFocus] = useState<FocusState | null>(null);
  const [anchor, setAnchor] = useState<EventAnchorRect | null>(null);

  const { data: blocks, loading: blocksLoading, error: blocksError } = usePlannerBlocks(from, to);
  const { data: overlay, loading: overlayLoading, error: overlayError } = useActualOverlay(
    from,
    to,
    refreshKey,
  );

  const { intervals, sleepIntervals } = useMemo(() => {
    const sleepSessions = overlay.filter(isSleepSession);
    const restSessions = overlay.filter((s) => !isSleepSession(s));
    const clipped = clipSessionsAgainstSleep(restSessions, sleepSessions);
    const toRows = (rows: ActualSession[]) =>
      rows
        .map(overlayToMergeable)
        .filter((row): row is NonNullable<typeof row> => row != null);
    return {
      intervals: mergeAdjacentIntervals(toRows(clipped)),
      sleepIntervals: mergeAdjacentIntervals(toRows(sleepSessions)),
    };
  }, [overlay]);

  const { axisStart, axisEnd } = computeAxisWindow(blocks, [...intervals, ...sleepIntervals], day);
  const hours = hourLabels(axisStart, axisEnd);
  const loading = blocksLoading || overlayLoading;

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
      width: evR.width,
      height: evR.height,
    });
    setFocus(next);
  }, []);

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
          if (t.closest('[role="dialog"]') || t.closest(".ribbon-segment")) return;
          setFocus(null);
          setAnchor(null);
        }}
      >
        <div className="flex items-center justify-between gap-2">
          <div>
            <h3 className="font-medium text-sm">Day ribbon — {dayLabel}</h3>
            <p className="text-[10px] text-muted-foreground mt-0.5">
              Watch sleep clips overnight PC time. Sessions within 2 minutes are grouped.
            </p>
          </div>
          {(blocksError || overlayError) && (
            <span className="text-[11px] text-muted-foreground">{blocksError || overlayError}</span>
          )}
        </div>

        <div className="relative min-w-0">
          <div className="relative h-4 mb-1">
            {hours.map((h, i) => {
              const pct = ((h * 60 - axisStart) / Math.max(1, axisEnd - axisStart)) * 100;
              const clamped = Math.min(100, Math.max(0, pct));
              // Keep tick alignment with tracks below; pin edge labels so they stay fully visible.
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
                    <span className="absolute inset-0 flex items-center justify-center text-[11px] text-muted-foreground">
                      No planned blocks
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
                        className="ribbon-segment absolute top-0 bottom-0 opacity-90 rounded-sm cursor-pointer hover:brightness-110 focus:outline-none focus:ring-1 focus:ring-violet-400/60"
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
                <div className="relative h-8 rounded-lg bg-white/5 overflow-hidden">
                  {intervals.length === 0 && sleepIntervals.length === 0 && (
                    <span className="absolute inset-0 flex items-center justify-center text-[11px] text-muted-foreground">
                      No tracked activity
                    </span>
                  )}
                  {sleepIntervals.map((iv, idx) => {
                    const clipped = minutesClippedToDay(iv.start_time, iv.end_time, day);
                    if (!clipped) return null;
                    const style = toSegmentStyle(clipped.startMin, clipped.endMin, axisStart, axisEnd);
                    return (
                      <button
                        key={`sleep-${iv.start_time}-${idx}`}
                        type="button"
                        className="ribbon-segment absolute top-0 bottom-0 rounded-sm cursor-pointer hover:brightness-110 focus:outline-none focus:ring-1 focus:ring-indigo-400/60 bg-indigo-500 opacity-80"
                        style={style}
                        title={mergedIntervalLabel(iv)}
                        onClick={(e) =>
                          openAt(e.currentTarget, {
                            kind: "actual",
                            interval: iv,
                            onPlan: false,
                            productive: false,
                            sleep: true,
                          })
                        }
                      />
                    );
                  })}
                  {intervals.map((iv, idx) => {
                    const clipped = minutesClippedToDay(iv.start_time, iv.end_time, day);
                    if (!clipped) return null;
                    const style = toSegmentStyle(clipped.startMin, clipped.endMin, axisStart, axisEnd);
                    const onPlan = actualOverlapsPlanned(clipped.startMin, clipped.endMin, blocks);
                    const productive = (iv.productivity_score ?? 0) >= PRODUCTIVE_THRESHOLD;
                    const segmentClass = onPlan
                      ? productive
                        ? "bg-emerald-500"
                        : "bg-rose-500"
                      : "bg-amber-500";
                    return (
                      <button
                        key={`${iv.start_time}-${idx}`}
                        type="button"
                        className={`ribbon-segment absolute top-0 bottom-0 rounded-sm cursor-pointer hover:brightness-110 focus:outline-none focus:ring-1 focus:ring-sky-400/60 ${segmentClass} opacity-85`}
                        style={style}
                        title={mergedIntervalLabel(iv)}
                        onClick={(e) =>
                          openAt(e.currentTarget, {
                            kind: "actual",
                            interval: iv,
                            onPlan,
                            productive,
                          })
                        }
                      />
                    );
                  })}
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
            <span className="text-sky-300/60">Click a segment for details</span>
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
