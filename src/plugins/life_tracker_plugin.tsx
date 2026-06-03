import { Heart, Monitor } from "lucide-react";
import type { PluginDef } from "./types";
import { registerPlugin } from "./registry";
import { LifeTrackerPage } from "../pages/LifeTrackerPage";
import { GoalTrackerProvider } from "../context/GoalTrackerContext";
import { BrowserActivityWidget, LifeScoreWidget } from "./LifeTrackerWidgets";

export const LifeTrackerPlugin: PluginDef = {
  id: "life-tracker",
  name: "Life & Behavior Tracker",
  description: "Track health, productivity, and digital wellbeing. Includes Chrome extension monitoring.",
  icon: Heart,
  isCore: false,
  Provider: GoalTrackerProvider,
  routes: [
    { path: "life-tracker", element: <LifeTrackerPage /> },
  ],
  navItems: [
    { to: "/life-tracker", label: "Life Tracker", icon: Heart, end: false },
  ],
  widgets: [
    {
      id: "browser-activity",
      type: "browser-activity",
      title: "Browser Activity",
      description: "Live feed from your SelfTracker extension.",
      icon: Monitor,
      accent: "from-indigo-500/20 to-violet-500/10",
      defaultColSpan: 2,
      component: <BrowserActivityWidget />
    },
    {
      id: "life-score",
      type: "life-score",
      title: "Life Score",
      description: "Daily health, productivity & wellbeing score.",
      icon: Heart,
      accent: "from-pink-500/20 to-rose-500/10",
      to: "/life-tracker",
      defaultColSpan: 1,
      defaultRowSpan: 2,
      component: <LifeScoreWidget />
    }
  ]
};

registerPlugin(LifeTrackerPlugin);
