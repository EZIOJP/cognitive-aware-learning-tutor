import type { ReactNode } from "react";
import { cn } from "../../app/components/ui/utils";

/** Scrollable settings sub-page inside AppShell (main uses overflow-hidden). */
export function SettingsPageScroll({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "h-full min-h-0 overflow-y-auto overflow-x-hidden overscroll-y-contain",
        className
      )}
    >
      {children}
    </div>
  );
}
