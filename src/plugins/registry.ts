/** Plugin definitions + registration (no React). */
export { registerPlugin, getAllPlugins, type PluginDef } from "./registryCore";

/** Plugin enable state & API sync. */
export {
  usePluginRegistry,
  usePlugins,
  usePluginsOptional,
  PluginRegistryProvider,
} from "./PluginRegistryProvider";
