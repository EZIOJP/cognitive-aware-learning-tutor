import { Settings2, BookOpen, Brain, Bot, Code2 } from "lucide-react";
import type { PluginDef } from "./types";
import { registerPlugin } from "./registry";
import { LectureNotesPage } from "../pages/study/LectureNotesPage";
import { ReviewHubPage } from "../pages/quiz/ReviewHubPage";

/** Shell only — settings and hub. Math, EEG, and trackers are separate plugins. */
export const CorePlugin: PluginDef = {
  id: "core",
  name: "Core Hub",
  description: "Dashboard, settings, central data hub, and account. Always on.",
  icon: Settings2,
  isCore: true,
  routes: [
    { path: "settings/plugins", element: <div className="p-6 text-sm text-muted-foreground">Plugin settings — coming soon.</div> },
    { path: "lecture-notes", element: <LectureNotesPage /> },
    { path: "review", element: <ReviewHubPage /> },
  ],
  navItems: [
    { to: "/lecture-notes", label: "Lecture Notes", icon: BookOpen, end: true },
    { to: "/review", label: "Review Hub", icon: Brain, end: true },
    { to: "/ai-coach", label: "AI Coach", icon: Bot, end: true },
    { to: "/project-agent", label: "Project Agent", icon: Code2, end: true },
  ],
  widgets: [],
};

registerPlugin(CorePlugin);
