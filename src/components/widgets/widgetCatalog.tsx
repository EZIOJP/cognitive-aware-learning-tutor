import { Activity, Calculator, LineChart } from "lucide-react";
import type { PluginWidget } from "../../plugins/types";
import { DesmosGraphWidget } from "./DesmosGraphWidget";
import { SymPyCalculatorWidget } from "./SymPyCalculatorWidget";

export type CatalogCategory = "all" | "study" | "math" | "health";

export interface CatalogEntry extends PluginWidget {
  category: "study" | "math" | "health";
  catalogOnly: true;
}

/** Optional hub widgets — user adds via Widget Picker. */
export const OPTIONAL_WIDGET_CATALOG: CatalogEntry[] = [
  {
    id: "desmos-graph",
    type: "tool",
    title: "Desmos Graph",
    description: "Plot equations inline — great for checking algebra.",
    icon: LineChart,
    accent: "from-sky-500/20 to-blue-500/10",
    defaultColSpan: 2,
    defaultRowSpan: 2,
    category: "math",
    catalogOnly: true,
    component: <DesmosGraphWidget />,
  },
  {
    id: "sympy-calculator",
    type: "tool",
    title: "SymPy Calculator",
    description: "Simplify, integrate, differentiate, or solve with SymPy.",
    icon: Calculator,
    accent: "from-indigo-500/20 to-violet-500/10",
    defaultColSpan: 1,
    defaultRowSpan: 2,
    category: "math",
    catalogOnly: true,
    component: <SymPyCalculatorWidget />,
  },
  {
    id: "train-ocr-link",
    type: "info",
    title: "Train my OCR",
    description: "Handwriting curriculum for TexTeller — opens when route is ready.",
    icon: Activity,
    accent: "from-emerald-500/20 to-teal-500/10",
    defaultColSpan: 1,
    category: "study",
    catalogOnly: true,
    to: "/math-tutor/train",
  },
];

export function getCatalogEntry(id: string): CatalogEntry | undefined {
  return OPTIONAL_WIDGET_CATALOG.find((w) => w.id === id);
}
