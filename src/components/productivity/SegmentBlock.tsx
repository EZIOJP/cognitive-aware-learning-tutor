import { CATEGORY_COLORS } from "../../api/plannerClient";
import type { SessionSegment } from "./hourSliceTypes";
import { abbreviateLabel } from "./hourSliceTypes";

function hashHue(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
  return h % 360;
}

export function segmentFill(seg: SessionSegment): string {
  if (seg.source === "sleep") {
    return "linear-gradient(165deg, rgba(99, 102, 241, 0.55) 0%, rgba(67, 56, 202, 0.65) 100%)";
  }
  const cat = (seg.category || "").toLowerCase();
  const known = CATEGORY_COLORS[cat];
  if (known) {
    return `linear-gradient(165deg, ${known}cc 0%, ${known}99 100%)`;
  }
  const hue = hashHue(seg.app_or_label || seg.session_group_id);
  return `linear-gradient(165deg, hsla(${hue}, 55%, 42%, 0.75) 0%, hsla(${hue}, 50%, 28%, 0.85) 100%)`;
}

type Props = {
  segment: SessionSegment;
  tier: "full" | "side" | "compressed" | "overflow";
  /** Continues from previous hour at min 0 — flat left edge */
  seamLeft: boolean;
  /** Continues into next hour at min 60 — flat right edge */
  seamRight: boolean;
  onClick?: (seg: SessionSegment, el: HTMLElement) => void;
};

export function SegmentBlock({ segment, tier, seamLeft, seamRight, onClick }: Props) {
  // Horizontal = minutes (0→60). Overlap allowed: full hour height, stack by z-index.
  const start = Math.max(0, Math.min(60, segment.start_min));
  const end = Math.max(start, Math.min(60, segment.end_min));
  const dur = Math.max(1, end - start);
  const leftPct = (start / 60) * 100;
  const widthPct = (dur / 60) * 100;
  // Above plan chips (z≈8–18) so concurrent apps stay clickable; shorter apps on top.
  const zIndex =
    segment.source === "sleep" ? 12 : 22 + Math.min(40, Math.round(60 - dur) + segment.lane_index);

  // Always paint a label when we can; narrow chips get a short abbrev (CSS ellipsizes).
  // Previously compressed hid labels below ~18% width (~11m), so 3–10m apps looked blank.
  const maxChars =
    tier === "full" || tier === "side"
      ? 24
      : widthPct >= 18
        ? 7
        : widthPct >= 10
          ? 4
          : widthPct >= 5
            ? 2
            : 1;
  const showLabel = maxChars >= 1 && (tier !== "overflow" || widthPct >= 4);
  const label =
    tier === "full" || tier === "side"
      ? segment.app_or_label
      : abbreviateLabel(segment.app_or_label, maxChars);

  const radiusLeft = seamLeft ? 0 : 6;
  const radiusRight = seamRight ? 0 : 6;

  return (
    <button
      type="button"
      className={`hour-seg-block hour-seg-overlap ${segment.source === "sleep" ? "hour-seg-sleep" : "hour-seg-desktop"}`}
      style={{
        left: `${leftPct}%`,
        width: `${widthPct}%`,
        top: 0,
        height: "100%",
        zIndex,
        background: segmentFill(segment),
        borderTopLeftRadius: radiusLeft,
        borderBottomLeftRadius: radiusLeft,
        borderTopRightRadius: radiusRight,
        borderBottomRightRadius: radiusRight,
        borderLeftWidth: seamLeft ? 0 : undefined,
        borderRightWidth: seamRight ? 0 : undefined,
      }}
      title={`${segment.app_or_label} · ${segment.start_min}–${segment.end_min}m`}
      onClick={(e) => {
        e.stopPropagation();
        onClick?.(segment, e.currentTarget);
      }}
    >
      {showLabel ? <span className="hour-seg-label">{label}</span> : null}
    </button>
  );
}
