/**
 * Curved SVG scrollbar that follows the container border-radius.
 * Hides the native scrollbar; thumb length tracks content ratio.
 */
import {
  useEffect,
  useRef,
  type CSSProperties,
  type ReactNode,
  type Ref,
  type UIEvent,
} from "react";
import { cn } from "../../app/components/ui/utils";

const OFFSET = 7;
const EXTRA_INSET = 2;
const MIN_START_RATIO = 0.8;
const MIN_THUMB = 20;
const SEGMENTS = 50;

export type CurvedScrollAreaProps = {
  children: ReactNode;
  className?: string;
  contentClassName?: string;
  /** Border radius in px (or CSS length). Default 28. */
  radius?: number | string;
  /** Accent variant for thumb. */
  tone?: "sky" | "lime" | "accent";
  style?: CSSProperties;
  contentRef?: Ref<HTMLDivElement>;
  /** Called when the inner content scrolls. */
  onScroll?: (e: UIEvent<HTMLDivElement>) => void;
};

function resolveRadiusPx(container: HTMLElement, radius?: number | string): number {
  if (typeof radius === "number" && Number.isFinite(radius)) return Math.max(0, radius);
  if (typeof radius === "string" && radius.trim()) {
    const n = parseFloat(radius);
    if (Number.isFinite(n)) return Math.max(0, n);
  }
  return parseFloat(getComputedStyle(container).borderRadius) || 0;
}

export function CurvedScrollArea({
  children,
  className,
  contentClassName,
  radius = 28,
  tone = "sky",
  style,
  contentRef,
  onScroll,
}: CurvedScrollAreaProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const innerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const container = containerRef.current;
    const content = innerRef.current;
    if (!container || !content) return;

    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.classList.add("curved-scrollbar__svg");
    svg.setAttribute("aria-hidden", "true");

    const trackPath = document.createElementNS("http://www.w3.org/2000/svg", "path");
    trackPath.classList.add("curved-scrollbar__track");
    const thumbPath = document.createElementNS("http://www.w3.org/2000/svg", "path");
    thumbPath.classList.add("curved-scrollbar__thumb");
    svg.appendChild(trackPath);
    svg.appendChild(thumbPath);
    container.appendChild(svg);

    let pathLength = 0;
    let thumbLength = 50;
    let dragging = false;
    let pointerId: number | null = null;

    const updateThumb = () => {
      if (pathLength <= 0) return;
      const scrollableHeight = content.scrollHeight - content.clientHeight || 1;
      const scrollRatio = content.scrollTop / scrollableHeight;
      const startOffset = (pathLength - thumbLength) * scrollRatio;
      const endOffset = startOffset + thumbLength;
      const points: string[] = [];
      for (let i = 0; i <= SEGMENTS; i++) {
        const t = startOffset + ((endOffset - startOffset) / SEGMENTS) * i;
        const p = trackPath.getPointAtLength(Math.max(0, Math.min(pathLength, t)));
        points.push(`${p.x} ${p.y}`);
      }
      thumbPath.setAttribute(
        "d",
        `M ${points[0]} ${points.slice(1).map((pt) => `L ${pt}`).join(" ")}`,
      );
      // Hide chrome when content fits.
      const needsScroll = content.scrollHeight > content.clientHeight + 2;
      svg.style.opacity = needsScroll ? "1" : "0";
      svg.style.pointerEvents = needsScroll ? "none" : "none";
      thumbPath.style.pointerEvents = needsScroll ? "auto" : "none";
    };

    const updatePath = () => {
      const w = container.clientWidth;
      const h = container.clientHeight;
      if (w < 8 || h < 8) return;
      const r = resolveRadiusPx(container, radius);
      const effectiveRadius = Math.max(r - OFFSET, 0);
      const trackX = w - OFFSET;
      const topY = OFFSET;
      const bottomY = h - OFFSET;
      const cornerX = trackX - effectiveRadius;
      const minStartX = w * MIN_START_RATIO;
      let startX = trackX - effectiveRadius * EXTRA_INSET;
      if (startX < minStartX) startX = minStartX;
      if (startX > cornerX) startX = cornerX;

      const d = [
        `M ${startX} ${topY}`,
        `L ${cornerX} ${topY}`,
        `A ${effectiveRadius} ${effectiveRadius} 0 0 1 ${trackX} ${topY + effectiveRadius}`,
        `L ${trackX} ${bottomY - effectiveRadius}`,
        `A ${effectiveRadius} ${effectiveRadius} 0 0 1 ${cornerX} ${bottomY}`,
        `L ${startX} ${bottomY}`,
      ].join(" ");
      trackPath.setAttribute("d", d);
      pathLength = trackPath.getTotalLength();
      const ratio = content.clientHeight / Math.max(1, content.scrollHeight);
      thumbLength = Math.max(MIN_THUMB, pathLength * Math.min(1, ratio));
      updateThumb();
    };

    const onPointerDown = (e: PointerEvent) => {
      e.preventDefault();
      dragging = true;
      pointerId = e.pointerId;
      thumbPath.setPointerCapture(pointerId);
    };

    const onPointerMove = (e: PointerEvent) => {
      if (!dragging || e.pointerId !== pointerId) return;
      const rect = container.getBoundingClientRect();
      let ratio = (e.clientY - rect.top) / Math.max(1, rect.height);
      ratio = Math.max(0, Math.min(1, ratio));
      content.scrollTop = ratio * (content.scrollHeight - content.clientHeight);
      updateThumb();
    };

    const onPointerUp = (e: PointerEvent) => {
      if (!dragging || e.pointerId !== pointerId) return;
      dragging = false;
      try {
        thumbPath.releasePointerCapture(pointerId);
      } catch {
        /* ignore */
      }
      pointerId = null;
    };

    thumbPath.addEventListener("pointerdown", onPointerDown);
    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", onPointerUp);
    content.addEventListener("scroll", updateThumb, { passive: true });
    window.addEventListener("resize", updatePath);

    const ro = new ResizeObserver(() => updatePath());
    ro.observe(container);
    ro.observe(content);

    updatePath();

    return () => {
      thumbPath.removeEventListener("pointerdown", onPointerDown);
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerup", onPointerUp);
      content.removeEventListener("scroll", updateThumb);
      window.removeEventListener("resize", updatePath);
      ro.disconnect();
      svg.remove();
    };
  }, [radius]);

  const setContentRef = (node: HTMLDivElement | null) => {
    innerRef.current = node;
    if (typeof contentRef === "function") contentRef(node);
    else if (contentRef && "current" in contentRef) {
      (contentRef as { current: HTMLDivElement | null }).current = node;
    }
  };

  return (
    <div
      ref={containerRef}
      className={cn(
        "curved-scrollbar",
        tone === "lime" && "curved-scrollbar--lime",
        tone === "accent" && "curved-scrollbar--accent",
        className,
      )}
      style={
        {
          ["--curved-radius" as string]:
            typeof radius === "number" ? `${radius}px` : radius,
          ...style,
        } as CSSProperties
      }
      data-scrollbar
    >
      <div
        ref={setContentRef}
        className={cn("curved-scrollbar__content", contentClassName)}
        onScroll={onScroll}
      >
        {children}
      </div>
    </div>
  );
}
