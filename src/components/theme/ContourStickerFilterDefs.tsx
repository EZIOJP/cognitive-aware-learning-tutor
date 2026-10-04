/**
 * True contour sticker — puffy / cloudy die-cut stack for ContourStickerLabel.
 * Morphology alone is boxy; we split expansion into morph + blur, then re-harden
 * so rings follow the word with soft bubble corners (not stair-steps).
 * Radii assume the label paints in a CONTOUR_SUPERSAMPLE× viewBox.
 */
import { useTheme } from "../../context/ThemeContext";
import type { SidebarStickerRing } from "../../theme/layers";

export const CONTOUR_LIVE_FILTER_ID = "calt-contour-live";

/** Maps tool-px → SVG user-space radius at 1× CSS font size. */
const RAIL_PX = 0.42;
/** Must match ContourStickerLabel live viewBox supersample. */
export const CONTOUR_SUPERSAMPLE = 2;
/** Preview / hero at near tool-px scale (also drawn in 2× viewBox). */
const HERO_PX = 0.95;

/**
 * Split a tool radius into morph (letter fidelity) + blur (cloudy round).
 * Heavy blur is what kills the Manhattan / stair-step silhouette.
 */
function puffyParams(radius: number) {
  const r = Math.max(1, radius);
  return {
    morph: Math.max(1, Math.round(r * 0.42)),
    blur: Math.max(1.1, r * 0.48),
    /** Extra polish pass — melts residual corners into soft lobes. */
    polish: Math.max(0.55, r * 0.16),
  };
}

function scaleRings(rings: SidebarStickerRing[], px: number): SidebarStickerRing[] {
  let prev = 0;
  return rings.map((r) => {
    const radius = Math.max(prev + 1, Math.round(r.radius * px));
    prev = radius;
    return { radius, color: r.color };
  });
}

/** Mount once under ThemeProvider — rebuilds when contour layers / scale change. */
export function ContourStickerFilterDefs() {
  const { sidebarStickerScale, sidebarStickerLayers } = useTheme();
  const t = sidebarStickerScale / 100;
  const rings = sidebarStickerLayers.rings;
  const live = scaleRings(rings, RAIL_PX * t * CONTOUR_SUPERSAMPLE);
  const hero = scaleRings(rings, HERO_PX * t * CONTOUR_SUPERSAMPLE);

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
        <ContourFilter id={CONTOUR_LIVE_FILTER_ID} rings={live} />
        <ContourFilter id={`${CONTOUR_LIVE_FILTER_ID}-hero`} rings={hero} />
      </defs>
    </svg>
  );
}

function ContourFilter({
  id,
  rings,
}: {
  id: string;
  rings: SidebarStickerRing[];
}) {
  // Softer re-harden than a hard clip — keeps a slight cloudy fringe.
  const slope = 9.5;
  const intercept = -2.8;
  // Paint outer → inner so thinner rings sit on top.
  const paintOrder = [...rings].reverse();
  const outerR = paintOrder[0]?.radius ?? 8;
  const cloudAa = Math.max(0.65, Math.min(2.4, outerR * 0.08));

  return (
    <filter
      id={id}
      x="-160%"
      y="-160%"
      width="420%"
      height="420%"
      filterUnits="userSpaceOnUse"
      primitiveUnits="userSpaceOnUse"
      colorInterpolationFilters="sRGB"
    >
      {paintOrder.flatMap((ring, i) => {
        const { morph, blur, polish } = puffyParams(ring.radius);
        const dil = `dil${i}`;
        const puff = `puff${i}`;
        const soft = `soft${i}`;
        const polishBlur = `polishBlur${i}`;
        const cloud = `cloud${i}`;
        const flood = `flood${i}`;
        const layer = `layer${i}`;
        return [
          // Light morph keeps counters / letter valleys; blur does most of the swell.
          <feMorphology
            key={`${id}-dil-${i}`}
            in="SourceAlpha"
            operator="dilate"
            radius={morph}
            result={dil}
          />,
          <feGaussianBlur
            key={`${id}-puff-${i}`}
            in={dil}
            stdDeviation={blur}
            result={puff}
          />,
          <feComponentTransfer key={`${id}-soft-${i}`} in={puff} result={soft}>
            <feFuncA type="linear" slope={slope} intercept={intercept} />
          </feComponentTransfer>,
          // Second soften — turns remaining right-angles into bubble lobes.
          <feGaussianBlur
            key={`${id}-polishBlur-${i}`}
            in={soft}
            stdDeviation={polish}
            result={polishBlur}
          />,
          <feComponentTransfer
            key={`${id}-cloud-${i}`}
            in={polishBlur}
            result={cloud}
          >
            <feFuncA type="linear" slope={12} intercept={-3.6} />
          </feComponentTransfer>,
          <feFlood
            key={`${id}-flood-${i}`}
            floodColor={ring.color}
            result={flood}
          />,
          <feComposite
            key={`${id}-layer-${i}`}
            in={flood}
            in2={cloud}
            operator="in"
            result={layer}
          />,
        ];
      })}

      <feMerge result="ringsHard">
        {paintOrder.map((_, i) => (
          <feMergeNode key={`${id}-merge-${i}`} in={`layer${i}`} />
        ))}
      </feMerge>
      {/* Cloudy fringe AA on rings only — glyph stays crisp on top */}
      <feGaussianBlur in="ringsHard" stdDeviation={cloudAa} result="ringsAa" />
      <feComponentTransfer in="ringsAa" result="rings">
        <feFuncA type="linear" slope={1.35} intercept={-0.04} />
      </feComponentTransfer>

      <feMerge result="stacked">
        <feMergeNode in="rings" />
        <feMergeNode in="SourceGraphic" />
      </feMerge>

      <feDropShadow
        in="stacked"
        dx="0"
        dy="1.5"
        stdDeviation="2.8"
        floodColor="#000000"
        floodOpacity="0.18"
      />
    </filter>
  );
}
