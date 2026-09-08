import type { ReactNode } from "react";
import { Activity } from "lucide-react";
import type { PluginDef } from "./types";
import { registerPlugin } from "./registry";
import { EegDashboardWidget } from "../components/dashboard/EegDashboardWidget";
import { EegSnapTestPage } from "../pages/EegSnapTestPage";

/** Marker provider — EEG stream is gated in StudySessionProvider when this plugin is enabled. */
export function EegPluginProvider({ children }: { children: ReactNode }) {
  return <>{children}</>;
}

export const EegPlugin: PluginDef = {
  id: "eeg",
  name: "EEG / Brain Activity",
  description:
    "ESP32 LED play over USB + optional UDP bands. Soft-fail if board is off.",
  icon: Activity,
  isCore: false,
  Provider: EegPluginProvider,
  routes: [{ path: "eeg", element: <EegSnapTestPage /> }],
  navItems: [{ to: "/eeg", label: "EEG", icon: Activity, end: true, category: "life" }],
  widgets: [
    {
      id: "eeg-status",
      type: "eeg",
      title: "Brain activity",
      description: "Snap test + alpha/beta/gamma when ESP32 streams.",
      icon: Activity,
      accent: "from-blue-500/20 to-cyan-500/10",
      defaultColSpan: 1,
      to: "/eeg",
      component: <EegDashboardWidget />,
    },
  ],
};

registerPlugin(EegPlugin);
