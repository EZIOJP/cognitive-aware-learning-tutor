import { Outlet } from "react-router";
import { AppSidebar } from "./AppSidebar";
import { AppTopBar } from "./AppTopBar";
import { FocusOverlay } from "../app/components/FocusOverlay";

export function AppShell() {
  return (
    <div className="flex h-screen w-screen overflow-hidden bg-background">
      <FocusOverlay />
      <AppSidebar />
      <div className="flex flex-col flex-1 min-w-0">
        <AppTopBar />
        <main className="flex-1 overflow-hidden p-3 sm:p-4">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
