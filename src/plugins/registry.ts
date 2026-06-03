import type { PluginDef } from "./types";

const ALL_PLUGINS: PluginDef[] = [];

export function registerPlugin(plugin: PluginDef) {
  if (!ALL_PLUGINS.find((p) => p.id === plugin.id)) {
    ALL_PLUGINS.push(plugin);
  }
}

export function getAllPlugins() {
  return ALL_PLUGINS;
}

/** Plugin enable state & API sync: use `usePluginRegistry` from `./PluginRegistryProvider`. */
export { usePluginRegistry, usePlugins, PluginRegistryProvider } from "./PluginRegistryProvider";
