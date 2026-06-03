import { Settings2 } from "lucide-react";
import type { PluginDef } from "./types";
import { registerPlugin } from "./registry";

/** Shell only — settings and hub. Math, EEG, and trackers are separate plugins. */
export const CorePlugin: PluginDef = {
  id: "core",
  name: "Core Hub",
  description: "Dashboard, settings, central data hub, and account. Always on.",
  icon: Settings2,
  isCore: true,
  routes: [{ path: "settings/plugins", element: <></> }],
  navItems: [],
  widgets: [],
};

registerPlugin(CorePlugin);
