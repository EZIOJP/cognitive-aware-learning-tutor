import { Settings2, BookOpen, Brain, PenLine } from "lucide-react";
import type { PluginDef } from "./types";
import { registerPlugin } from "./registry";
import { LectureNotesPage } from "../pages/study/LectureNotesPage";
import { ReviewHubPage } from "../pages/quiz/ReviewHubPage";

/** Shell only — settings and study loop. Math, EEG, and trackers are separate plugins. */
export const CorePlugin: PluginDef = {
  id: "core",
  name: "Core Hub",
  description: "Dashboard, settings, and account. Always on.",
  icon: Settings2,
  isCore: true,
  routes: [
    { path: "settings/plugins", element: <div className="p-6 text-sm text-muted-foreground">Plugin settings — coming soon.</div> },
    { path: "lecture-notes", element: <LectureNotesPage /> },
    { path: "review", element: <ReviewHubPage /> },
  ],
  navItems: [
    { to: "/journal", label: "Journal", icon: PenLine, end: true },
    { to: "/lecture-notes", label: "Lecture Notes", icon: BookOpen, end: true },
    { to: "/review", label: "Study Loop", icon: Brain, end: true },
  ],
  widgets: [],
};

registerPlugin(CorePlugin);
