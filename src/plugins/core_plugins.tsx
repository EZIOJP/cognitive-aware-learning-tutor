import { Brain, BookOpen, Settings2 } from "lucide-react";
import type { PluginDef } from "./types";
import { registerPlugin } from "./registry";
import { MathDashboardPage } from "../pages/MathDashboardPage";
import { MathTopicPage } from "../pages/math/MathTopicPage";
import { MathPracticePage } from "../pages/math/MathPracticePage";
import { MathReportsPage } from "../pages/math/MathReportsPage";
import { GreVocabPage } from "../pages/GreVocabPage";
import { VocabReadPage } from "../pages/vocab/VocabReadPage";
import { VocabCyclePage } from "../pages/vocab/VocabCyclePage";

// ─────────────────────────────────────────────────────────
// Core Plugin (Math Tutor + Settings)
// ─────────────────────────────────────────────────────────
export const CorePlugin: PluginDef = {
  id: "core",
  name: "Core Features",
  description: "Essential tools: Math Tutor and system settings.",
  icon: Settings2,
  isCore: true,
  routes: [
    { path: "math-tutor", element: <MathDashboardPage /> },
    { path: "math-tutor/topic/:topicId", element: <MathTopicPage /> },
    { path: "math-tutor/practice/:topicId", element: <MathPracticePage /> },
    { path: "math-tutor/reports", element: <MathReportsPage /> },
    { path: "settings/plugins", element: <></> }
  ],
  navItems: [
    { to: "/math-tutor", label: "Math Tutor", icon: Brain, end: false },
  ],
  widgets: [
    // We could move study time widget here
  ]
};

// ─────────────────────────────────────────────────────────
// GRE Vocab Plugin
// ─────────────────────────────────────────────────────────
export const VocabPlugin: PluginDef = {
  id: "gre-vocab",
  name: "GRE Vocabulary",
  description: "Comprehensive GRE word study with active recall and spacing.",
  icon: BookOpen,
  isCore: false,
  routes: [
    { path: "gre-vocab", element: <GreVocabPage /> },
    { path: "gre-vocab/read", element: <VocabReadPage /> },
    { path: "gre-vocab/read/:mode", element: <VocabReadPage /> },
    { path: "gre-vocab/cycle", element: <VocabCyclePage /> },
  ],
  navItems: [
    { to: "/gre-vocab", label: "GRE Vocab", icon: BookOpen, end: false },
  ],
};

// Register them immediately
registerPlugin(CorePlugin);
registerPlugin(VocabPlugin);
