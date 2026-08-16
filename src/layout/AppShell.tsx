import { Outlet } from "react-router";
import { useEffect } from "react";
import { AppSidebar } from "./AppSidebar";
import { AppTopBar } from "./AppTopBar";
import { FocusOverlay } from "../app/components/FocusOverlay";
import { MorningGateRedirect } from "../components/MorningGateRedirect";
import { useStudyPresenceHeartbeat } from "../hooks/useStudyPresenceHeartbeat";
import { startDataPipelineWatch } from "../utils/dataPipelineBus";
import { DashboardChromeProvider } from "../context/DashboardChromeContext";

export function AppShell() {
  useEffect(() => startDataPipelineWatch(), []);
  useStudyPresenceHeartbeat();

  return (
    <DashboardChromeProvider>
      <div className="flex h-screen w-screen overflow-hidden bg-background">
        <FocusOverlay />
        <MorningGateRedirect />
        <AppSidebar />
        <div className="flex flex-col flex-1 min-w-0">
          <AppTopBar />
          <main className="flex-1 min-h-0 overflow-y-auto p-3 sm:p-4">
            <Outlet />
          </main>
        </div>
      </div>
    </DashboardChromeProvider>
  );
}
