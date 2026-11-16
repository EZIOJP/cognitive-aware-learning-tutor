/**
 * Glass scroll area — straight modern scrollbar (thin / nearly invisible).
 * Keeps the CurvedScrollArea name for call sites; no bent SVG chrome.
 */
import {
  type CSSProperties,
  type ReactNode,
  type Ref,
  type UIEvent,
} from "react";
import { cn } from "../../app/components/ui/utils";

export type CurvedScrollAreaProps = {
  children: ReactNode;
  className?: string;
  contentClassName?: string;
  /** Kept for API compat; unused (no curved path). */
  radius?: number | string;
  /** Accent variant for glass thumb. */
  tone?: "sky" | "lime" | "accent";
  style?: CSSProperties;
  contentRef?: Ref<HTMLDivElement>;
  /** Called when the inner content scrolls. */
  onScroll?: (e: UIEvent<HTMLDivElement>) => void;
};

export function CurvedScrollArea({
  children,
  className,
  contentClassName,
  tone = "sky",
  style,
  contentRef,
  onScroll,
}: CurvedScrollAreaProps) {
  return (
    <div
      className={cn(
        "glass-scrollbar",
        "curved-scrollbar",
        tone === "lime" && "glass-scrollbar--lime curved-scrollbar--lime",
        tone === "accent" && "glass-scrollbar--accent curved-scrollbar--accent",
        className,
      )}
      style={style}
      data-scrollbar="glass"
    >
      <div
        ref={contentRef}
        className={cn("glass-scrollbar__content", "curved-scrollbar__content", contentClassName)}
        onScroll={onScroll}
      >
        {children}
      </div>
    </div>
  );
}
