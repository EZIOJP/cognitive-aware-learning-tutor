/**
 * slim/life-core branch: keep only daily-life study surfaces.
 * Flip to false (or set VITE_SLIM_LIFE_CORE=0) to restore full nav on this branch.
 */
export const SLIM_LIFE_CORE =
  import.meta.env.VITE_SLIM_LIFE_CORE === "0"
    ? false
    : import.meta.env.VITE_SLIM_LIFE_CORE === "1"
      ? true
      : true; // default ON for slim/life-core branch

/** Plugins that stay enabled in slim mode (core is always on). */
export const SLIM_PLUGIN_IDS = new Set(["core", "productivity", "life-tracker"]);

/** Core nav destinations kept in slim mode. */
export const SLIM_CORE_NAV_PATHS = new Set([
  "/journal",
  "/lecture-notes",
  "/system-logs",
  "/ai-coach",
]);

/** Core routes kept in slim mode (path without leading slash). */
export const SLIM_CORE_ROUTE_PATHS = new Set([
  "settings/plugins",
  "lecture-notes",
  "system-logs",
]);
