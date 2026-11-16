/**
 * Contour sticker helpers. Rings are glyph strokes (see ContourStickerLabel),
 * not a blurred blob. This file only hosts the drop shadow and the
 * tool-px → user-space outset used by both the rail and the settings preview.
 */
import type { SidebarStickerRing } from "../../theme/layers";

export const CONTOUR_SHADOW_FILTER_ID = "calt-contour-shadow";

/** Must match ContourStickerLabel viewBox supersample. */
export const CONTOUR_SUPERSAMPLE = 2;

/**
 * Tool dilation px → CSS outset at 100% title size.
 * Kept under 1 so a default outer ring hugs the word instead of swallowing it.
 */
const RAIL_PX = 0.34;
const HERO_PX = 0.72;

/** Outset in SVG user px (already × supersample) for one ring. */
export function contourOutsetUserPx(
  toolRadius: number,
  scalePercent: number,
  variant: "live" | "hero",
): number {
  const px = variant === "hero" ? HERO_PX : RAIL_PX;
  const t = (Number.isFinite(scalePercent) ? scalePercent : 100) / 100;
  return Math.max(0.8, toolRadius * px * t * CONTOUR_SUPERSAMPLE);
}

/** Inner → outer tool rings, strictly increasing, in user px. */
export function contourOutsetsUserPx(
  rings: SidebarStickerRing[],
  scalePercent: number,
  variant: "live" | "hero",
): number[] {
  let prev = 0;
  return rings.map((ring) => {
    const next = Math.max(prev + 0.8, contourOutsetUserPx(ring.radius, scalePercent, variant));
    prev = next;
    return next;
  });
}

/** Mount once under ThemeProvider. */
export function ContourStickerFilterDefs() {
  return (
    <svg
      aria-hidden
      focusable="false"
      width={0}
      height={0}
      className="pointer-events-none absolute"
      style={{ position: "absolute", width: 0, height: 0, overflow: "hidden" }}
    >
      <defs>
        <filter
          id={CONTOUR_SHADOW_FILTER_ID}
          x="-40%"
          y="-40%"
          width="180%"
          height="180%"
          colorInterpolationFilters="sRGB"
        >
          <feDropShadow
            dx="0"
            dy="3"
            stdDeviation="2.2"
            floodColor="#000000"
            floodOpacity="0.28"
          />
        </filter>
      </defs>
    </svg>
  );
}
