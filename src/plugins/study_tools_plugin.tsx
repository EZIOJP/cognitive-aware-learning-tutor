import { Wrench } from "lucide-react";
import type { PluginDef } from "./types";
import { registerPlugin } from "./registry";
import { OPTIONAL_WIDGET_CATALOG } from "../components/widgets/widgetCatalog";

export const StudyToolsPlugin: PluginDef = {
  id: "study-tools",
  name: "Study Tools",
  description: "Desmos graph, SymPy calculator, and other hub widgets.",
  icon: Wrench,
  isCore: true,
  widgets: OPTIONAL_WIDGET_CATALOG,
};

registerPlugin(StudyToolsPlugin);
