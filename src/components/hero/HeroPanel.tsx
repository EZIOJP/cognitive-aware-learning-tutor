import type { ReactNode } from "react";
import { cn } from "../../app/components/ui/utils";

interface HeroPanelProps {
  children: ReactNode;
  className?: string;
}

/** Optional comic/gloss panel — respects html[data-surface-style] */
export function HeroPanel({ children, className }: HeroPanelProps) {
  return (
    <div className={cn("gloss-panel hero-panel rounded-xl p-4", className)}>
      {children}
    </div>
  );
}
