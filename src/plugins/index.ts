export * from "./types";
export * from "./registry";

// Import all plugins to ensure they are registered
import "./core_plugins";
import "./life_tracker_plugin";
import "./nutrinode/index";
