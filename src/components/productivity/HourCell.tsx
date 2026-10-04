import type { HourSlice, SessionSegment } from "./hourSliceTypes";
import { complexityTier } from "./hourSliceTypes";
import { SegmentBlock } from "./SegmentBlock";

type Props = {
  slice: HourSlice;
  /** session_group_ids continuing from previous hour */
  contFromPrev: Set<string>;
  /** session_group_ids continuing into next hour */
  contIntoNext: Set<string>;
  onSegmentClick?: (seg: SessionSegment, el: HTMLElement) => void;
  onOverflowClick?: (hidden: SessionSegment[], el: HTMLElement) => void;
};

const MINUTE_MARKS = [0, 15, 30, 45, 60] as const;

/** Horizontal 0–60 minute scale (left → right). Used as sticky top axis. */
export function HourMinuteScale({ compact = false }: { compact?: boolean }) {
  return (
    <div
      className={`hour-minute-scale${compact ? " hour-minute-scale--compact" : ""}`}
      aria-hidden
      data-minute-axis="0-60"
    >
      {MINUTE_MARKS.map((m) => (
        <span
          key={m}
          className={`hour-minute-scale__mark${m === 0 || m === 60 ? " hour-minute-scale__mark--edge" : ""}`}
          style={{ left: `${(m / 60) * 100}%` }}
        >
          <span className="hour-minute-scale__tick" />
          <span className="hour-minute-scale__label">{m}</span>
        </span>
      ))}
    </div>
  );
}

export function HourCell({ slice, contFromPrev, contIntoNext, onSegmentClick }: Props) {
  const tier = complexityTier(slice.lane_count);
  // Paint every sample on the same vertical band; concurrent apps overlap by time.
  const shown = slice.segments;

  return (
    <div className={`hour-cell hour-cell--${tier}`} data-hour={slice.hour} data-overlap="1">
      <div className="hour-cell__body">
        {shown.map((seg) => {
          const key = `${seg.session_group_id}:${seg.start_min}:${seg.end_min}`;
          return (
            <SegmentBlock
              key={key}
              segment={seg}
              tier={tier}
              seamLeft={contFromPrev.has(seg.session_group_id) && seg.start_min === 0}
              seamRight={contIntoNext.has(seg.session_group_id) && seg.end_min === 60}
              onClick={onSegmentClick}
            />
          );
        })}
      </div>
    </div>
  );
}
