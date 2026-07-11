import { createContext, type ReactNode } from "react";
import type { HubCustomFeature } from "../api/hubClient";
import type { PluginDef, PluginNavItem, PluginRoute, PluginWidget } from "./types";

export type RegistryContextValue = {
  enabledIds: string[];
  customFeatures: HubCustomFeature[];
  isLoaded: boolean;
  syncError: string | null;
  togglePlugin: (id: string, enabled: boolean) => Promise<void>;
  refreshFromServer: () => Promise<void>;
  allPlugins: PluginDef[];
  activePlugins: PluginDef[];
  getRoutes: () => PluginRoute[];
  getNavItems: () => PluginNavItem[];
  getWidgets: () => PluginWidget[];
  getProviders: () => Array<({ children }: { children: ReactNode }) => ReactNode>;
};

/** Shared context module — keep separate so HMR / circular imports don't fork Provider vs consumer. */
export const RegistryContext = createContext<RegistryContextValue | null>(null);
