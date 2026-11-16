import { Outlet } from "react-router";
import { useEffect } from "react";
import { AppSidebar, SIDEBAR_RAIL_PX } from "./AppSidebar";
import { AppTopBar } from "./AppTopBar";
import { FocusOverlay } from "../app/components/FocusOverlay";
import { MorningGateRedirect } from "../components/MorningGateRedirect";
import { useStudyPresenceHeartbeat } from "../hooks/useStudyPresenceHeartbeat";
import { startDataPipelineWatch } from "../utils/dataPipelineBus";
import { DashboardChromeProvider } from "../context/DashboardChromeContext";
import { isFocusDesktopShell } from "../utils/focusDesktopShell";
import { cn } from "../app/components/ui/utils";

/** Left gutter reserved for the auto-hide rail (expanded drawer overlays on top). */
export const SIDEBAR_RAIL_INSET = `${SIDEBAR_RAIL_PX}px`;

export function AppShell() {
  useEffect(() => startDataPipelineWatch(), []);
  useStudyPresenceHeartbeat();
  const focusShell = isFocusDesktopShell();

  return (
    <DashboardChromeProvider>
      <div
        className={cn(
          "relative flex h-screen w-screen overflow-hidden bg-background",
          focusShell && "focus-shell-root",
        )}
      >
        <FocusOverlay />
        <MorningGateRedirect />
        <AppSidebar />
        <div
          className="flex min-w-0 flex-1 flex-col"
          style={{ paddingLeft: SIDEBAR_RAIL_INSET }}
        >
          <AppTopBar />
          <main
            className={cn(
              "flex-1 min-h-0 overflow-y-auto",
              focusShell
                ? "focus-shell-main overflow-hidden px-0 py-0"
                : "px-3 py-4 sm:px-4 sm:py-5",
            )}
          >
            <Outlet />
          </main>
        </div>
      </div>
    </DashboardChromeProvider>
  );
}
