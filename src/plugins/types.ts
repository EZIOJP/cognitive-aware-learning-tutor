import type { ReactNode } from "react";

export interface PluginRoute {
  path: string;
  element: ReactNode;
  children?: PluginRoute[];
}

export interface PluginNavItem {
  to: string;
  label: string;
  icon: any; // Lucide icon
  end?: boolean;
}

export interface PluginWidget {
  id: string;
  type: string;
  title: string;
  description: string;
  content?: string;
  icon: any;
  accent: string;
  to?: string;
  component?: ReactNode;
  /** How many grid columns this widget spans by default (1 or 2). Default: 1 */
  defaultColSpan?: 1 | 2;
  /** How many grid rows this widget spans by default (1 or 2). Default: 1 */
  defaultRowSpan?: 1 | 2;
  /** When true, widget is only added via Widget Picker (not auto-shown on dashboard). */
  catalogOnly?: boolean;
  /** Picker grouping — Study, Math, Health */
  category?: "study" | "math" | "health";
}

export interface PluginDef {
  id: string;
  name: string;
  description: string;
  icon: any;
  // If true, it cannot be disabled by the user
  isCore?: boolean;
  
  routes?: PluginRoute[];
  navItems?: PluginNavItem[];
  widgets?: PluginWidget[];
  
  // A wrapper component to provide context to the whole app
  Provider?: ({ children }: { children: ReactNode }) => ReactNode;
}
