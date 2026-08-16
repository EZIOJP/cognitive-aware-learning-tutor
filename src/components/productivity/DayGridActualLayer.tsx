import { useEffect, useMemo, useState, type RefObject } from "react";
import { format } from "date-fns";
import type { HourSlice, SessionSegment } from "./hourSliceTypes";
import { HourCell, HourMinuteScale } from "./HourCell";
import { slicesForDay } from "./HourSliceProvider";
import { PlanHourSegBlock } from "./PlanHourSegBlock";
import { segsByHour, type PlanHourSeg } from "./planHourSegments";

type Props = {
  day: Date;
  slices: HourSlice[];
  /** Plan blocks split onto the 0–60 minute X-axis (2D track). */
  planSegs?: PlanHourSeg[];
  focusedPlanId?: number | null;
  containerRef: RefObject<HTMLDivElement | null>;
  onSegmentClick: (seg: SessionSegment, hourStart: Date, el: HTMLElement) => void;
  onOverflowClick: (hidden: SessionSegment[], hourStart: Date, el: HTMLElement) => void;
  onPlanSegClick?: (seg: PlanHourSeg, el: HTMLElement) => void;
};

type SlotGeom = { top: number; height: number; left: number; width: number };
type RulerGeom = { top: number; left: number; width: number };

function measureDaySlots(wrap: HTMLElement): {
  column: SlotGeom;
  hours: SlotGeom[];
  ruler: RulerGeom;
} | null {
  const daySlot = wrap.querySelector(".rbc-time-content .rbc-day-slot") as HTMLElement | null;
  const content = wrap.querySelector(".rbc-time-content") as HTMLElement | null;
  if (!daySlot || !content) return null;

  const wrapR = wrap.getBoundingClientRect();
  const dayR = daySlot.getBoundingClientRect();
  const contentR = content.getBoundingClientRect();

  // Sticky top axis: pinned to the visible top of the time grid (day column only).
  const ruler: RulerGeom = {
    top: Math.max(0, contentR.top - wrapR.top),
    left: dayR.left - wrapR.left,
    width: dayR.width,
  };

  const column: SlotGeom = {
    top: dayR.top - wrapR.top + wrap.scrollTop,
    left: dayR.left - wrapR.left + wrap.scrollLeft,
    width: dayR.width,
    height: dayR.height,
  };

  const groups = Array.from(daySlot.querySelectorAll(".rbc-timeslot-group")) as HTMLElement[];
  if (groups.length === 0) {
    const h = dayR.height / 24;
    return {
      column,
      ruler,
      hours: Array.from({ length: 24 }, (_, i) => ({
        top: column.top + i * h,
        height: h,
        left: column.left,
        width: column.width,
      })),
    };
  }

  return {
    column,
    ruler,
    hours: groups.map((g) => {
      const r = g.getBoundingClientRect();
      return {
        top: r.top - wrapR.top + wrap.scrollTop,
        height: r.height,
        left: column.left,
        width: column.width,
      };
    }),
  };
}

export function DayGridActualLayer({
  day,
  slices,
  planSegs = [],
  focusedPlanId = null,
  containerRef,
  onSegmentClick,
  onOverflowClick,
  onPlanSegClick,
}: Props) {
  const dayKey = format(day, "yyyy-MM-dd");
  const daySlices = useMemo(() => slicesForDay(slices, dayKey), [slices, dayKey]);
  const byHour = useMemo(() => {
    const m = new Map<number, HourSlice>();
    for (const s of daySlices) m.set(s.hour, s);
    return m;
  }, [daySlices]);
  const plansByHour = useMemo(() => segsByHour(planSegs), [planSegs]);

  const [geom, setGeom] = useState<{
    column: SlotGeom;
    hours: SlotGeom[];
    ruler: RulerGeom;
  } | null>(null);

  useEffect(() => {
    const wrap = containerRef.current;
    if (!wrap) return;

    const update = () => setGeom(measureDaySlots(wrap));
    update();
    const ro = new ResizeObserver(update);
    ro.observe(wrap);
    const content = wrap.querySelector(".rbc-time-content");
    if (content) {
      ro.observe(content);
      content.addEventListener("scroll", update, { passive: true });
    }
    wrap.addEventListener("scroll", update, true);
    const t = window.setTimeout(update, 80);
    return () => {
      ro.disconnect();
      content?.removeEventListener("scroll", update);
      wrap.removeEventListener("scroll", update, true);
      window.clearTimeout(t);
    };
  }, [containerRef, dayKey, daySlices.length, planSegs.length]);

  const continuity = useMemo(() => {
    const fromPrev = new Map<number, Set<string>>();
    const intoNext = new Map<number, Set<string>>();
    for (let h = 0; h < 24; h++) {
      fromPrev.set(h, new Set());
      intoNext.set(h, new Set());
    }
    for (let h = 0; h < 23; h++) {
      const a = byHour.get(h);
      const b = byHour.get(h + 1);
      if (!a || !b) continue;
      const aIds = new Set(
        a.segments.filter((s) => s.end_min === 60).map((s) => s.session_group_id),
      );
      const bIds = new Set(
        b.segments.filter((s) => s.start_min === 0).map((s) => s.session_group_id),
      );
      for (const id of aIds) {
        if (bIds.has(id)) {
          intoNext.get(h)!.add(id);
          fromPrev.get(h + 1)!.add(id);
        }
      }
    }
    return { fromPrev, intoNext };
  }, [byHour]);

  if (!geom) return null;

  const hourCount = geom.hours.length || 24;

  return (
    <div className="day-grid-actual-layer" aria-hidden={false}>
      {/* Full-height vertical rails at 15 / 30 / 45 — aligned with top minute axis */}
      <div
        className="day-grid-minute-rails"
        style={{
          position: "absolute",
          top: geom.column.top,
          left: geom.column.left,
          width: geom.column.width,
          height: geom.column.height,
          zIndex: 1,
          pointerEvents: "none",
        }}
        aria-hidden
      />

      {/* Persistent 0–60 minute axis — same left/width as day column so block edges align */}
      <div
        className="day-grid-minute-ruler"
        style={{
          position: "absolute",
          top: geom.ruler.top,
          left: geom.ruler.left,
          width: geom.ruler.width,
          zIndex: 12,
          pointerEvents: "none",
        }}
        title="Minutes within each hour (0–60). Plan and activity blocks map left→right to start/end minutes."
      >
        <HourMinuteScale />
      </div>

      {Array.from({ length: hourCount }, (_, hour) => {
        const slice = byHour.get(hour);
        const plans = plansByHour.get(hour) ?? [];
        const slot = geom.hours[hour];
        if (!slot) return null;
        const hourStart = new Date(day);
        hourStart.setHours(hour, 0, 0, 0);
        return (
          <div
            key={hour}
            className="day-grid-hour-slot"
            style={{
              position: "absolute",
              top: slot.top,
              left: slot.left,
              width: slot.width,
              height: slot.height,
              pointerEvents: "none",
            }}
          >
            <div style={{ position: "relative", width: "100%", height: "100%", pointerEvents: "none" }}>
              {/* Plans under tracked chips so overlapping short apps stay clickable / cycle-reachable */}
              {plans.map((p) => (
                <PlanHourSegBlock
                  key={`plan-${p.blockId}-${p.hour}-${p.start_min}-${p.end_min}`}
                  seg={p}
                  focused={focusedPlanId === p.blockId}
                  onClick={onPlanSegClick}
                />
              ))}
              {slice ? (
                <HourCell
                  slice={slice}
                  contFromPrev={continuity.fromPrev.get(hour) ?? new Set()}
                  contIntoNext={continuity.intoNext.get(hour) ?? new Set()}
                  onSegmentClick={(seg, el) => onSegmentClick(seg, hourStart, el)}
                  onOverflowClick={(hidden, el) => onOverflowClick(hidden, hourStart, el)}
                />
              ) : (
                <div className="hour-cell hour-cell--empty" />
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
