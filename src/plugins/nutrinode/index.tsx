import { Apple } from "lucide-react";
import type { PluginDef } from "../types";
import { registerPlugin } from "../registry";

import { NutritionPage } from "./NutritionPage";
import { NutritionWidget } from "./NutritionWidget";
import { NutritionProvider } from "./NutritionContext";

export const NutriNodePlugin: PluginDef = {
  id: "nutrinode",
  name: "NutriNode",
  description: "Hardware-backed nutrition tracking using ESP32-CAM and Claude Vision.",
  icon: Apple,
  isCore: false,
  Provider: NutritionProvider,
  routes: [
    { path: "nutrition", element: <NutritionPage /> },
  ],
  navItems: [
    { to: "/nutrition", label: "Nutrition", icon: Apple, end: false },
  ],
  widgets: [
    {
      id: "nutrition",
      type: "nutrition",
      title: "Today's Macros",
      description: "Live feed from your NutriNode scale.",
      icon: Apple,
      accent: "from-emerald-500/20 to-green-500/10",
      to: "/nutrition",
      defaultColSpan: 2,
      component: <NutritionWidget />
    }
  ]
};

// Register it!
registerPlugin(NutriNodePlugin);
