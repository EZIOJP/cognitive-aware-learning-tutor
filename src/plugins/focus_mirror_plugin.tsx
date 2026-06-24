import type { PluginDef } from "./types";
import { registerPlugin } from "./registry";
import { ScanFace } from "lucide-react";
import { CalibrationPage } from "../pages/CalibrationPage";
import { FaceTrackerProvider } from "../face-tracker/FaceTrackerContext";

/** Browser face tracker (Human) with per-setup calibration; Python mirror stays as legacy. */
export const FocusMirrorPlugin: PluginDef = {
  id: "focus-mirror",
  name: "Focus Mirror",
  description:
    "In-browser webcam attention tracking with per-setup calibration profiles. Hub metric: face_attention.",
  icon: ScanFace,
  isCore: false,
  Provider: FaceTrackerProvider,
  routes: [{ path: "focus/calibrate", element: <CalibrationPage /> }],
  navItems: [],
  widgets: [
    {
      id: "focus-mirror-hint",
      type: "focus-mirror",
      title: "Focus mirror",
      description: "Start tracking from the top bar — calibrate per setup first.",
      icon: ScanFace,
      accent: "from-emerald-500/20 to-teal-500/10",
      defaultColSpan: 1,
      content: "Global browser tracker; red border during unfocused Pomodoro sessions.",
    },
  ],
};

registerPlugin(FocusMirrorPlugin);
