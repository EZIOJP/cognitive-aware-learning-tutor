import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";

export interface WidgetState {
  colSpan: 1 | 2;
  rowSpan: 1 | 2;
  hidden: boolean;
}

export type WidgetStateMap = Record<string, WidgetState>;

export interface DashboardWidget {
  id: string;
  title: string;
  icon: LucideIcon;
  accent: string;
  component: ReactNode;
  defaultColSpan?: 1 | 2;
  defaultRowSpan?: 1 | 2;
  to?: string;
}

export function loadWidgetState(key: string): WidgetStateMap {
  try {
    const s = localStorage.getItem(`${key}:state`);
    return s ? JSON.parse(s) : {};
  } catch {
    return {};
  }
}

export function saveWidgetState(key: string, map: WidgetStateMap) {
  localStorage.setItem(`${key}:state`, JSON.stringify(map));
}

export function loadWidgetOrder(key: string, widgets: DashboardWidget[]): DashboardWidget[] {
  try {
    const raw = localStorage.getItem(`${key}:order`);
    if (!raw) return widgets;
    const ids = JSON.parse(raw) as string[];
    const ordered = ids
      .map((id) => widgets.find((w) => w.id === id))
      .filter(Boolean) as DashboardWidget[];
    const missing = widgets.filter((w) => !ids.includes(w.id));
    return [...ordered, ...missing];
  } catch {
    return widgets;
  }
}

export function saveWidgetOrder(key: string, widgets: DashboardWidget[]) {
  localStorage.setItem(`${key}:order`, JSON.stringify(widgets.map((w) => w.id)));
}
