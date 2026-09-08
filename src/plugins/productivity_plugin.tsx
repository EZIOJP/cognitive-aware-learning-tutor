import { Monitor, Crosshair } from "lucide-react";
import type { PluginDef } from "./types";
import { registerPlugin } from "./registry";
import { ProductivityPage } from "../pages/ProductivityPage";
import FocusPage from "../pages/FocusPage";

export const ProductivityPlugin: PluginDef = {
  id: "productivity",
  name: "Productivity Tracker",
  description: "Desktop app usage, planner, and screen-time tracking.",
  icon: Monitor,
  routes: [
    { path: "productivity", element: <ProductivityPage /> },
    { path: "productivity/focus", element: <FocusPage /> },
  ],
  navItems: [
    { to: "/productivity/focus", label: "Focus", icon: Crosshair, end: true, category: "focus" },
    { to: "/productivity", label: "Calendar", icon: Monitor, end: true, category: "focus" },
  ],
  widgets: [],
};

registerPlugin(ProductivityPlugin);
