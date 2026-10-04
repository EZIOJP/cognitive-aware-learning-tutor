/**
 * High-DPI contour title — SVG <text> + shared filter, painted in a 2×
 * viewBox then displayed at 1× CSS size (true supersample, not CSS scale-blur).
 */
import { useLayoutEffect, useMemo, useState } from "react";
import { CONTOUR_LIVE_FILTER_ID, CONTOUR_SUPERSAMPLE } from "./ContourStickerFilterDefs";
import { cn } from "../../app/components/ui/utils";

type Props = {
  text: string;
  /** Visual (CSS) font size in px */
  fontSizePx: number;
  fontFamily: string;
  fill: string;
  className?: string;
  /** Use hero filter (1× radii) for large previews — default live (2× radii). */
  variant?: "live" | "hero";
};

function measureTextWidth(text: string, fontPx: number, fontFamily: string): number {
  if (typeof document === "undefined") return Math.max(80, text.length * fontPx * 0.55);
  const canvas = document.createElement("canvas");
  const ctx = canvas.getContext("2d");
  if (!ctx) return Math.max(80, text.length * fontPx * 0.55);
  ctx.font = `400 ${fontPx}px ${fontFamily}`;
  return Math.max(24, ctx.measureText(text || " ").width);
}

export function ContourStickerLabel({
  text,
  fontSizePx,
  fontFamily,
  fill,
  className,
  variant = "live",
}: Props) {
  const label = text.trim() || "Focus";
  const ss = variant === "live" ? CONTOUR_SUPERSAMPLE : 2;
  const filterId = variant === "live" ? CONTOUR_LIVE_FILTER_ID : `${CONTOUR_LIVE_FILTER_ID}-hero`;

  const [widthPx, setWidthPx] = useState(() => measureTextWidth(label, fontSizePx, fontFamily));

  useLayoutEffect(() => {
    setWidthPx(measureTextWidth(label, fontSizePx, fontFamily));
  }, [label, fontSizePx, fontFamily]);

  const dims = useMemo(() => {
    // Tight box — contour filter region carries the halo; keep only glyph padding.
    const padX = fontSizePx * 0.42;
    const cssW = widthPx + padX * 2;
    const cssH = fontSizePx * 1.35;
    return {
      cssW,
      cssH,
      vbW: cssW * ss,
      vbH: cssH * ss,
      font: fontSizePx * ss,
    };
  }, [widthPx, fontSizePx, ss]);

  return (
    <svg
      className={cn("contour-sticker-label block overflow-visible", className)}
      width={dims.cssW}
      height={dims.cssH}
      viewBox={`0 0 ${dims.vbW} ${dims.vbH}`}
      aria-label={label}
      role="img"
      style={{ maxWidth: "none", height: "auto", overflow: "visible" }}
    >
      <text
        x={dims.vbW / 2}
        y={dims.vbH / 2}
        textAnchor="middle"
        dominantBaseline="central"
        fontFamily={fontFamily}
        fontSize={dims.font}
        fontWeight={400}
        fill={fill}
        filter={`url(#${filterId})`}
        style={{
          paintOrder: "normal",
        }}
      >
        {label}
      </text>
    </svg>
  );
}
