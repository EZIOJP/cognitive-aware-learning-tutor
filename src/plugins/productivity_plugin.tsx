import { Monitor } from "lucide-react";
import type { PluginDef } from "./types";
import { registerPlugin } from "./registry";
import { ProductivityPage } from "../pages/ProductivityPage";

export const ProductivityPlugin: PluginDef = {
  id: "productivity",
  name: "Productivity Tracker",
  description: "Desktop app usage, planner, and screen-time tracking.",
  icon: Monitor,
  routes: [
    { path: "productivity", element: <ProductivityPage /> },
  ],
  navItems: [
    { to: "/productivity", label: "Productivity", icon: Monitor, end: true },
  ],
  widgets: [],
};

registerPlugin(ProductivityPlugin);
