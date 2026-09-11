import { Monitor } from "lucide-react";
import type { PluginDef } from "./types";
import { registerPlugin } from "./registry";
import { ProductivityPage } from "../pages/ProductivityPage";
import FocusPage from "../pages/FocusPage";
import { OpenFocusInterstitial } from "../components/productivity/OpenFocusInterstitial";
import { isFocusDesktopShell } from "../utils/focusDesktopShell";

function ProductivityRoute() {
  if (!isFocusDesktopShell()) return <OpenFocusInterstitial />;
  return <ProductivityPage />;
}

function FocusRoute() {
  if (!isFocusDesktopShell()) return <OpenFocusInterstitial />;
  return <FocusPage />;
}

export const ProductivityPlugin: PluginDef = {
  id: "productivity",
  name: "Productivity Tracker",
  description: "Desktop app usage, planner, and screen-time tracking.",
  icon: Monitor,
  routes: [
    { path: "productivity", element: <ProductivityRoute /> },
    { path: "productivity/focus", element: <FocusRoute /> },
  ],
  // Phase 0: Study sidebar must not advertise Productivity — Focus is the sole door.
  navItems: [],
  widgets: [],
};

registerPlugin(ProductivityPlugin);
