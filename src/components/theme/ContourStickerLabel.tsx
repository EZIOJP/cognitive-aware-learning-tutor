/**
 * Contour title — each ring is a round stroke on the glyph outline, so the
 * layers wrap the letters (swashes and descenders included). The SVG box
 * includes that outset plus the drop shadow, so the sidebar pad is real
 * space around the sticker instead of a clipped overflow.
 */
import { useLayoutEffect, useMemo, useRef, useState } from "react";
import { useTheme } from "../../context/ThemeContext";
import { cn } from "../../app/components/ui/utils";
import {
  CONTOUR_SHADOW_FILTER_ID,
  CONTOUR_SUPERSAMPLE,
  contourOutsetsUserPx,
} from "./ContourStickerFilterDefs";

type Props = {
  text: string;
  /** Visual (CSS) font size in px */
  fontSizePx: number;
  fontFamily: string;
  fill: string;
  className?: string;
  /** Hero uses a slightly larger outset for big previews. */
  variant?: "live" | "hero";
};

type Ink = {
  left: number;
  right: number;
  ascent: number;
  descent: number;
};

function measureInk(text: string, fontPx: number, fontFamily: string): Ink {
  const fallback: Ink = {
    left: fontPx * 0.14,
    right: Math.max(fontPx * 2, text.length * fontPx * 0.5),
    ascent: fontPx * 1.08,
    descent: fontPx * 0.46,
  };
  if (typeof document === "undefined") return fallback;
  const canvas = document.createElement("canvas");
  const ctx = canvas.getContext("2d");
  if (!ctx) return fallback;
  ctx.font = `400 ${fontPx}px ${fontFamily}`;
  ctx.textAlign = "left";
  ctx.textBaseline = "alphabetic";
  const m = ctx.measureText(text || " ");
  const ascent = m.actualBoundingBoxAscent;
  const right = m.actualBoundingBoxRight;
  if (!ascent || !right) {
    return { ...fallback, right: Math.max(fallback.right, m.width || fallback.right) };
  }
  return {
    left: Math.max(0, m.actualBoundingBoxLeft || 0),
    right: Math.max(m.width || 0, right),
    ascent,
    descent: Math.max(m.actualBoundingBoxDescent || 0, fontPx * 0.08),
  };
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
  const { sidebarStickerScale, sidebarStickerLayers } = useTheme();
  const ss = CONTOUR_SUPERSAMPLE;
  const coreRef = useRef<SVGTextElement>(null);

  const [ink, setInk] = useState<Ink>(() => measureInk(label, fontSizePx, fontFamily));
  /** User-space viewport fitted to the glyphs + stroke + shadow. */
  const [frame, setFrame] = useState<{ x: number; y: number; w: number; h: number } | null>(null);

  useLayoutEffect(() => {
    let cancelled = false;
    const apply = () => {
      if (!cancelled) setInk(measureInk(label, fontSizePx, fontFamily));
    };
    apply();
    const spec = `400 ${fontSizePx}px ${fontFamily}`;
    const fonts = document.fonts;
    if (fonts?.load) {
      fonts.load(spec).then(apply).catch(() => {});
      fonts.ready.then(apply).catch(() => {});
    }
    return () => {
      cancelled = true;
    };
  }, [label, fontSizePx, fontFamily]);

  const dims = useMemo(() => {
    const outs = contourOutsetsUserPx(sidebarStickerLayers.rings, sidebarStickerScale, variant);
    const outerUser = outs.length ? outs[outs.length - 1] : 0;
    const outerCss = outerUser / ss;
    // Provisional box until getBBox fits the real glyphs. Shadow stays inside it.
    const shadowCss = 10;
    const pad = outerCss + shadowCss;
    const cssW = ink.left + ink.right + pad * 2;
    const cssH = ink.ascent + ink.descent + pad * 2;
    return {
      cssW,
      cssH,
      vbW: cssW * ss,
      vbH: cssH * ss,
      font: fontSizePx * ss,
      x: (pad + ink.left) * ss,
      y: (pad + ink.ascent) * ss,
      outs,
      outerUser,
    };
  }, [ink, fontSizePx, sidebarStickerLayers.rings, sidebarStickerScale, variant, ss]);

  useLayoutEffect(() => {
    const el = coreRef.current;
    if (!el) return;
    const b = el.getBBox();
    if (!b.width || !b.height) return;
    // Stroke sits outside the fill. Shadow (dy 3, blur 2.2) needs a bit more.
    const pad = dims.outerUser + 18;
    const next = {
      x: b.x - pad,
      y: b.y - pad,
      w: b.width + pad * 2,
      h: b.height + pad * 2,
    };
    setFrame((prev) => {
      if (
        prev &&
        Math.abs(prev.x - next.x) < 0.6 &&
        Math.abs(prev.y - next.y) < 0.6 &&
        Math.abs(prev.w - next.w) < 0.6 &&
        Math.abs(prev.h - next.h) < 0.6
      ) {
        return prev;
      }
      return next;
    });
  }, [label, fontSizePx, fontFamily, fill, dims.x, dims.y, dims.font, dims.outerUser, sidebarStickerLayers.rings]);

  const view = frame ?? { x: 0, y: 0, w: dims.vbW, h: dims.vbH };

  const paint = [...sidebarStickerLayers.rings]
    .map((ring, i) => ({ color: ring.color, outset: dims.outs[i] ?? 0 }))
    .sort((a, b) => b.outset - a.outset);

  const textProps = {
    x: dims.x,
    y: dims.y,
    textAnchor: "start" as const,
    dominantBaseline: "alphabetic" as const,
    fontFamily,
    fontSize: dims.font,
    fontWeight: 400,
  };

  return (
    <svg
      className={cn("contour-sticker-label block", className)}
      width={view.w / ss}
      height={view.h / ss}
      viewBox={`${view.x} ${view.y} ${view.w} ${view.h}`}
      aria-label={label}
      role="img"
    >
      <g filter={`url(#${CONTOUR_SHADOW_FILTER_ID})`}>
        {paint.map((ring) => (
          <text
            key={`${ring.color}-${ring.outset}`}
            {...textProps}
            fill={ring.color}
            stroke={ring.color}
            strokeWidth={ring.outset * 2}
            strokeLinejoin="round"
            strokeLinecap="round"
          >
            {label}
          </text>
        ))}
        <text ref={coreRef} {...textProps} fill={fill}>
          {label}
        </text>
      </g>
    </svg>
  );
}
