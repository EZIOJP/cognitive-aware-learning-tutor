import { forwardRef, useCallback, useEffect, useRef, useState } from "react";
import { blockColor } from "../../api/plannerClient";
import type { PlannerBlock } from "../../api/plannerClient";
import { useDesktopTimeline, usePlannerBlocks } from "../../hooks/usePlanVsActual";
import { ActivityDetailPanel, type EventAnchorRect } from "./ActivityDetailPanel";
import {
  actualOverlapsPlanned,
  computeAxisWindow,
  endOfDay,
  fmtDurationMinutes,
  mergeAdjacentIntervals,
  mergedIntervalLabel,
  minutesSinceMidnight,
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
  | { kind: "actual"; interval: MergedInterval; onPlan: boolean; productive: boolean }
  | { kind: "planned"; block: PlannerBlock };

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

  const [localRefresh, setLocalRefresh] = useState(0);
  const { data: blocks, loading: blocksLoading, error: blocksError } = usePlannerBlocks(from, to);
  const { data: timeline, loading: timelineLoading, error: timelineError } = useDesktopTimeline(
    dayStr,
    refreshKey + localRefresh,
  );

  const intervals = mergeAdjacentIntervals(
    (timeline?.intervals ?? []).map((iv) => ({
      session_id: iv.session_id,
      start_time: iv.start_time,
      end_time: iv.end_time,
      app_name: iv.app_name,
      category: iv.category,
      window_title: iv.window_title,
      site: iv.site ?? null,
      productivity_score: iv.productivity_score,
      duration_seconds: iv.duration_seconds,
    })),
  );
  const { axisStart, axisEnd } = computeAxisWindow(blocks, intervals);
  const hours = hourLabels(axisStart, axisEnd);
  const loading = blocksLoading || timelineLoading;

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
              Sessions within 2 minutes are grouped for this timeline.
            </p>
          </div>
          {(blocksError || timelineError) && (
            <span className="text-[11px] text-muted-foreground">{blocksError || timelineError}</span>
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
                    const s0 = minutesSinceMidnight(new Date(b.start_at));
                    const s1 = minutesSinceMidnight(new Date(b.end_at));
                    const style = toSegmentStyle(s0, s1, axisStart, axisEnd);
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
                  {intervals.length === 0 && (
                    <span className="absolute inset-0 flex items-center justify-center text-[11px] text-muted-foreground">
                      No tracked activity
                    </span>
                  )}
                  {intervals.map((iv, idx) => {
                    if (!iv.start_time || !iv.end_time) return null;
                    const s0 = minutesSinceMidnight(new Date(iv.start_time));
                    const s1 = minutesSinceMidnight(new Date(iv.end_time));
                    const style = toSegmentStyle(s0, s1, axisStart, axisEnd);
                    const onPlan = actualOverlapsPlanned(s0, s1, blocks);
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
              focus.onPlan
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
