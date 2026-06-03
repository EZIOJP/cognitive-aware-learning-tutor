import { useState, useEffect } from "react";
import type { PluginDef, PluginNavItem, PluginRoute, PluginWidget } from "./types";
import { Brain, Heart, Activity } from "lucide-react"; // Default icons for core plugins

// A global registry of all available plugins
const ALL_PLUGINS: PluginDef[] = [];

export function registerPlugin(plugin: PluginDef) {
  if (!ALL_PLUGINS.find(p => p.id === plugin.id)) {
    ALL_PLUGINS.push(plugin);
  }
}

export function getAllPlugins() {
  return ALL_PLUGINS;
}

const LS_KEY = "active_plugins";

// Custom hook to manage enabled plugins
export function usePlugins() {
  const [enabledIds, setEnabledIds] = useState<string[]>([]);
  const [isLoaded, setIsLoaded] = useState(false);

  useEffect(() => {
    try {
      const saved = localStorage.getItem(LS_KEY);
      if (saved) {
        setEnabledIds(JSON.parse(saved));
      } else {
        // By default, enable all core plugins + any others
        setEnabledIds(ALL_PLUGINS.map(p => p.id));
      }
    } catch {
      setEnabledIds(ALL_PLUGINS.map(p => p.id));
    } finally {
      setIsLoaded(true);
    }
  }, []);

  const togglePlugin = (id: string, enabled: boolean) => {
    const plugin = ALL_PLUGINS.find(p => p.id === id);
    if (plugin?.isCore) return; // Cannot disable core plugins

    setEnabledIds(prev => {
      const next = enabled ? [...prev, id] : prev.filter(pId => pId !== id);
      localStorage.setItem(LS_KEY, JSON.stringify(next));
      return next;
    });
  };

  const activePlugins = ALL_PLUGINS.filter(p => p.isCore || enabledIds.includes(p.id));

  // Helper to aggregate features from active plugins
  const getRoutes = (): PluginRoute[] => activePlugins.flatMap(p => p.routes || []);
  const getNavItems = (): PluginNavItem[] => activePlugins.flatMap(p => p.navItems || []);
  const getWidgets = (): PluginWidget[] => activePlugins.flatMap(p => p.widgets || []);
  const getProviders = () => activePlugins.map(p => p.Provider).filter(Boolean);

  return {
    allPlugins: ALL_PLUGINS,
    enabledIds,
    togglePlugin,
    activePlugins,
    getRoutes,
    getNavItems,
    getWidgets,
    getProviders,
    isLoaded
  };
}
