export * from "./types";
export * from "./registry";

// Import all plugins to ensure they are registered
import "./core_plugins";
import "./gre_vocab_plugin";
import "./math_tutor_plugin";
import "./eeg_plugin";
import "./focus_mirror_plugin";
import "./life_tracker_plugin";
import "./nutrinode/index";
