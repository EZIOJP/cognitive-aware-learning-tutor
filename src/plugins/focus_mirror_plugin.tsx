import type { PluginDef } from "./types";
import { registerPlugin } from "./registry";
import { ScanFace } from "lucide-react";
import { CalibrationPage } from "../pages/CalibrationPage";

/** Python OpenCV mirror — backend/face_tracker.py posts face_attention to the hub. */
export const FocusMirrorPlugin: PluginDef = {
  id: "focus-mirror",
  name: "Focus Mirror",
  description:
    "Desktop mirrored webcam + attention from Python (face_tracker.py). Hub metric: face_attention.",
  icon: ScanFace,
  isCore: false,
  routes: [{ path: "focus/calibrate", element: <CalibrationPage /> }],
  navItems: [],
  widgets: [
    {
      id: "focus-mirror-hint",
      type: "focus-mirror",
      title: "Focus mirror",
      description: "Run scripts\\run_face_tracker.bat with the backend up.",
      icon: ScanFace,
      accent: "from-emerald-500/20 to-teal-500/10",
      defaultColSpan: 1,
      content: "Mirrored OpenCV window; status appears in the top bar when running.",
    },
  ],
};

registerPlugin(FocusMirrorPlugin);
