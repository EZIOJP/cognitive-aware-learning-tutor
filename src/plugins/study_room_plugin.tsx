import { LayoutTemplate } from "lucide-react";
import type { PluginDef } from "./types";
import { registerPlugin } from "./registry";
import { StudyRoomPage } from "../pages/study/StudyRoomPage";

export const StudyRoomPlugin: PluginDef = {
  id: "study-room",
  name: "Study Room",
  description: "Infinite canvas with OCR Recognize, Socratic Ask, and Desmos.",
  icon: LayoutTemplate,
  isCore: false,
  routes: [{ path: "study-room", element: <StudyRoomPage /> }],
  navItems: [{ to: "/study-room", label: "Study Room", icon: LayoutTemplate, end: true }],
};

registerPlugin(StudyRoomPlugin);
