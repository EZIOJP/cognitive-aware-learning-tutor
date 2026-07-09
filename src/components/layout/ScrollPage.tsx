import type { ReactNode } from "react";

/** Standard scrollable page shell — matches Productivity / Life Tracker. */
export function ScrollPage({ children }: { children: ReactNode }) {
  return (
    <div className="h-full min-h-0 overflow-y-auto bg-background text-foreground">
      <div className="max-w-3xl mx-auto p-4 sm:p-6 pb-24">{children}</div>
    </div>
  );
}
