import type { ReactNode } from "react";
import { Activity } from "lucide-react";
import type { PluginDef } from "./types";
import { registerPlugin } from "./registry";
import { EegDashboardWidget } from "../components/dashboard/EegDashboardWidget";

/** Marker provider — EEG stream is gated in StudySessionProvider when this plugin is enabled. */
export function EegPluginProvider({ children }: { children: ReactNode }) {
  return <>{children}</>;
}

export const EegPlugin: PluginDef = {
  id: "eeg",
  name: "EEG / Brain Activity",
  description:
    "Simulated attention now; plug in ESP32 UDP later (software ready). Cognitive load + hub eeg_attention.",
  icon: Activity,
  isCore: false,
  Provider: EegPluginProvider,
  widgets: [
    {
      id: "eeg-status",
      type: "eeg",
      title: "Brain activity",
      description: "Alpha / beta / gamma — simulation until ESP32 is connected.",
      icon: Activity,
      accent: "from-blue-500/20 to-cyan-500/10",
      defaultColSpan: 1,
      component: <EegDashboardWidget />,
    },
  ],
};

registerPlugin(EegPlugin);
