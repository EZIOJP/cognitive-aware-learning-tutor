import { BookOpen } from "lucide-react";
import type { PluginDef } from "./types";
import { registerPlugin } from "./registry";
import { GreVocabPage } from "../pages/GreVocabPage";
import { VocabReadPage } from "../pages/vocab/VocabReadPage";
import { VocabCyclePage } from "../pages/vocab/VocabCyclePage";

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
  navItems: [{ to: "/gre-vocab", label: "GRE Vocab", icon: BookOpen, end: false }],
};

registerPlugin(VocabPlugin);
