import {
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { Sparkles } from "lucide-react";
import { useAuthOptional } from "../context/AuthContext";
import {
  BACKEND_PLUGIN_TO_FRONTEND,
  fetchHubPluginsState,
  setHubPlugin,
  type HubCustomFeature,
} from "../api/hubClient";
import { getAllPlugins } from "./registryCore";
import type { PluginNavItem, PluginRoute, PluginWidget } from "./types";
import { CustomFeaturePage } from "./custom/CustomFeaturePage";
import { CustomFeatureWidget } from "./custom/CustomFeatureWidget";
import { RegistryContext, type RegistryContextValue } from "./registryContext";

export type { RegistryContextValue };

const LS_KEY = "active_plugins";

function defaultEnabledPluginIds(): string[] {
  const defaultOn = new Set([
    "math-tutor",
    "gre-vocab",
    "life-tracker",
    "study-room",
    "productivity",
    "eeg",
  ]);
  return getAllPlugins().filter((p) => p.isCore || defaultOn.has(p.id)).map((p) => p.id);
}

function backendStateToFrontendIds(plugins: { plugin_id: string; enabled: boolean }[]): string[] {
  const ids = new Set<string>();
  for (const row of plugins) {
    if (!row.enabled) continue;
    const mapped = BACKEND_PLUGIN_TO_FRONTEND[row.plugin_id] ?? [row.plugin_id];
    for (const id of mapped) {
      if (getAllPlugins().some((p) => p.id === id)) ids.add(id);
    }
  }
  for (const p of getAllPlugins()) {
    if (p.isCore) ids.add(p.id);
  }
  return [...ids];
}

export function PluginRegistryProvider({ children }: { children: ReactNode }) {
  // Optional: avoid white-screen if Vite HMR briefly orphans AuthContext.
  const isAuthenticated = Boolean(useAuthOptional()?.isAuthenticated);
  const [enabledIds, setEnabledIds] = useState<string[]>([]);
  const [customFeatures, setCustomFeatures] = useState<HubCustomFeature[]>([]);
  const [isLoaded, setIsLoaded] = useState(false);
  const [syncError, setSyncError] = useState<string | null>(null);

  const loadLocal = useCallback(() => {
    try {
      const saved = localStorage.getItem(LS_KEY);
      let ids: string[] = saved ? JSON.parse(saved) : defaultEnabledPluginIds();
      // Ensure ESP32 / EEG LED page is reachable for existing installs
      if (!ids.includes("eeg") && getAllPlugins().some((p) => p.id === "eeg")) {
        ids = [...ids, "eeg"];
        localStorage.setItem(LS_KEY, JSON.stringify(ids));
      }
      setEnabledIds(ids);
    } catch {
      setEnabledIds(defaultEnabledPluginIds());
    }
  }, []);

  const refreshFromServer = useCallback(async () => {
    if (!isAuthenticated) {
      loadLocal();
      setCustomFeatures([]);
      setIsLoaded(true);
      return;
    }
    try {
      const state = await Promise.race([
        fetchHubPluginsState(),
        new Promise<null>((resolve) => setTimeout(() => resolve(null), 4000)),
      ]);
      if (!state) {
        loadLocal();
        setSyncError("Could not sync features from server — using local settings.");
        setIsLoaded(true);
        return;
      }
      setSyncError(null);
      let frontendIds = backendStateToFrontendIds(state.plugins);
      if (!frontendIds.includes("eeg") && getAllPlugins().some((p) => p.id === "eeg")) {
        frontendIds = [...frontendIds, "eeg"];
        void setHubPlugin("eeg", true);
      }
      // Focus shell must always keep productivity enabled
      if (typeof window !== "undefined") {
        const h = window.location.hostname;
        const focusShell =
          window.location.protocol === "file:" ||
          h === "calt.app" ||
          h.endsWith(".calt.app") ||
          ((h === "127.0.0.1" || h === "localhost") && window.location.port === "5174");
        if (focusShell && !frontendIds.includes("productivity")) {
          frontendIds = [...frontendIds, "productivity"];
        }
      }
      setEnabledIds(frontendIds);
      localStorage.setItem(LS_KEY, JSON.stringify(frontendIds));
      setCustomFeatures((state.custom_features ?? []).filter((f) => f.enabled));
      setIsLoaded(true);
    } catch {
      loadLocal();
      setSyncError("Could not sync features from server — using local settings.");
      setIsLoaded(true);
    }
  }, [isAuthenticated, loadLocal]);

  useEffect(() => {
    // Paint immediately from localStorage — never block the shell on hub API.
    loadLocal();
    setIsLoaded(true);
    void refreshFromServer();
  }, [refreshFromServer, loadLocal]);

  const togglePlugin = useCallback(
    async (id: string, enabled: boolean) => {
      const plugin = getAllPlugins().find((p) => p.id === id);
      if (plugin?.isCore) return;

      setEnabledIds((prev) => {
        const next = enabled ? [...new Set([...prev, id])] : prev.filter((pId) => pId !== id);
        localStorage.setItem(LS_KEY, JSON.stringify(next));
        return next;
      });

      if (isAuthenticated) {
        const backendId =
          Object.entries(BACKEND_PLUGIN_TO_FRONTEND).find(([, fronts]) => fronts.includes(id))?.[0] ?? id;
        const ok = await setHubPlugin(backendId, enabled);
        if (!ok) setSyncError("Failed to save plugin preference on server.");
        else setSyncError(null);
      }
    },
    [isAuthenticated]
  );

  const codedActive = useMemo(
    () => getAllPlugins().filter((p) => p.isCore || enabledIds.includes(p.id)),
    [enabledIds]
  );

  const customRoutes: PluginRoute[] = useMemo(
    () =>
      customFeatures.map((f) => ({
        path: `features/${f.feature_id}`,
        element: <CustomFeaturePage featureId={f.feature_id} />,
      })),
    [customFeatures]
  );

  const customNav: PluginNavItem[] = useMemo(
    () =>
      customFeatures.map((f) => ({
        to: `/features/${f.feature_id}`,
        label: f.name,
        icon: Sparkles,
        end: false,
      })),
    [customFeatures]
  );

  const customWidgets: PluginWidget[] = useMemo(
    () =>
      customFeatures.map((f) => ({
        id: f.feature_id,
        type: "custom-feature",
        title: f.name,
        description: f.description || "Your custom feature",
        icon: Sparkles,
        accent: "from-violet-500/20 to-fuchsia-500/10",
        to: `/features/${f.feature_id}`,
        defaultColSpan: 1 as const,
        component: <CustomFeatureWidget feature={f} />,
      })),
    [customFeatures]
  );

  const value = useMemo<RegistryContextValue>(
    () => ({
      enabledIds,
      customFeatures,
      isLoaded,
      syncError,
      togglePlugin,
      refreshFromServer,
      allPlugins: getAllPlugins(),
      activePlugins: codedActive,
      getRoutes: () => [...codedActive.flatMap((p) => p.routes || []), ...customRoutes],
      getNavItems: () => [...codedActive.flatMap((p) => p.navItems || []), ...customNav],
      getWidgets: () => [...codedActive.flatMap((p) => p.widgets || []), ...customWidgets],
      getProviders: () =>
        codedActive
          .map((p) => p.Provider)
          .filter((P): P is NonNullable<typeof P> => Boolean(P)),
    }),
    [
      enabledIds,
      customFeatures,
      isLoaded,
      syncError,
      togglePlugin,
      refreshFromServer,
      codedActive,
      customRoutes,
      customNav,
      customWidgets,
    ]
  );

  return <RegistryContext.Provider value={value}>{children}</RegistryContext.Provider>;
}

export function usePluginRegistry(): RegistryContextValue {
  const ctx = useContext(RegistryContext);
  if (!ctx) throw new Error("usePluginRegistry must be used within PluginRegistryProvider");
  return ctx;
}

/** Safe for early providers / HMR — returns null outside PluginRegistryProvider. */
export function usePluginsOptional(): RegistryContextValue | null {
  return useContext(RegistryContext);
}

/** @deprecated Use usePluginRegistry — kept for gradual migration */
export function usePlugins() {
  return usePluginRegistry();
}
