import type { ReactNode } from "react";
import { cn } from "../../app/components/ui/utils";
import { isFocusDesktopShell } from "../../utils/focusDesktopShell";

/** Standard scrollable page shell — matches Productivity / Life Tracker. */
export function ScrollPage({ children }: { children: ReactNode }) {
  const focusShell = isFocusDesktopShell();
  return (
    <div
      className={cn(
        "h-full min-h-0 bg-background text-foreground",
        focusShell ? "focus-shell-page-root overflow-visible" : "overflow-y-auto",
      )}
    >
      <div className="max-w-3xl mx-auto p-4 sm:p-6 pb-24">{children}</div>
    </div>
  );
}
