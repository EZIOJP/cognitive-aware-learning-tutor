import { Brain } from "lucide-react";
import type { PluginDef } from "./types";
import { registerPlugin } from "./registry";
import { MathDashboardPage } from "../pages/MathDashboardPage";
import { MathTopicPage } from "../pages/math/MathTopicPage";
import { MathPracticePage } from "../pages/math/MathPracticePage";
import { MathReportsPage } from "../pages/math/MathReportsPage";
import { MathRecognizeTestPage } from "../pages/math/MathRecognizeTestPage";
import { TrainPlaygroundPage } from "../pages/math/TrainPlaygroundPage";

export const MathTutorPlugin: PluginDef = {
  id: "math-tutor",
  name: "Math Tutor",
  description:
    "Practice, whiteboard, and reports. Pairs with EEG plugin for cognitive load during sessions.",
  icon: Brain,
  isCore: false,
  routes: [
    { path: "math-tutor", element: <MathDashboardPage /> },
    { path: "math-tutor/topic/:topicId", element: <MathTopicPage /> },
    { path: "math-tutor/practice/:topicId", element: <MathPracticePage /> },
    { path: "math-tutor/reports", element: <MathReportsPage /> },
    { path: "math-tutor/recognize-test", element: <MathRecognizeTestPage /> },
    { path: "math-tutor/train", element: <TrainPlaygroundPage /> },
  ],
  navItems: [{ to: "/math-tutor", label: "Math Tutor", icon: Brain, end: false }],
};

registerPlugin(MathTutorPlugin);
