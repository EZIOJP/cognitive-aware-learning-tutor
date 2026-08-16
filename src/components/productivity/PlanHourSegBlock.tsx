import { blockColor } from "../../api/plannerClient";
import type { PlanHourSeg } from "./planHourSegments";

type Props = {
  seg: PlanHourSeg;
  focused?: boolean;
  onClick?: (seg: PlanHourSeg, el: HTMLElement) => void;
};

function fmtClock(hour: number, min: number): string {
  const h24 = min >= 60 ? hour + 1 : hour;
  const m = min >= 60 ? 0 : min;
  const h12 = ((h24 + 11) % 12) + 1;
  const ap = h24 >= 12 ? "PM" : "AM";
  return `${h12}:${String(m).padStart(2, "0")} ${ap}`;
}

/** Plan block on the 2D minute axis — solid color + time (distinct from tracked-app chips). */
export function PlanHourSegBlock({ seg, focused, onClick }: Props) {
  const start = Math.max(0, Math.min(59, seg.start_min));
  const end = Math.max(start + 1, Math.min(60, seg.end_min));
  const leftPct = (start / 60) * 100;
  const widthPct = ((end - start) / 60) * 100;
  const color = blockColor(seg.category, seg.color);
  const radiusLeft = seg.seamLeft ? 0 : 6;
  const radiusRight = seg.seamRight ? 0 : 6;
  const faded = seg.status === "done" || seg.status === "cancelled";
  const timeStart = fmtClock(seg.hour, start);
  const timeEnd = end === 60 ? fmtClock(seg.hour + 1, 0) : fmtClock(seg.hour, end);
  const timeLine = `${timeStart} – ${timeEnd}`;
  const showTime = widthPct >= 12;

  return (
    <button
      type="button"
      className={`hour-seg-block hour-seg-plan${focused ? " hour-seg-plan--focused" : ""}${
        seg.isDraft ? " hour-seg-plan--draft" : ""
      }${faded ? " hour-seg-plan--faded" : ""}`}
      style={{
        left: `${leftPct}%`,
        width: `${widthPct}%`,
        top: "6%",
        height: "88%",
        zIndex: 8 + Math.min(10, Math.round(60 - (end - start))),
        backgroundColor: color,
        borderColor: color,
        borderTopLeftRadius: radiusLeft,
        borderBottomLeftRadius: radiusLeft,
        borderTopRightRadius: radiusRight,
        borderBottomRightRadius: radiusRight,
        borderLeftWidth: seg.seamLeft ? 0 : 3,
        borderRightWidth: seg.seamRight ? 0 : undefined,
      }}
      title={`${seg.title} · ${timeLine}`}
      onClick={(e) => {
        e.stopPropagation();
        onClick?.(seg, e.currentTarget);
      }}
    >
      <span className="hour-seg-plan__inner">
        {showTime ? <span className="hour-seg-plan__time">{timeLine}</span> : null}
        <span className="hour-seg-plan__title">{seg.title}</span>
      </span>
    </button>
  );
}
