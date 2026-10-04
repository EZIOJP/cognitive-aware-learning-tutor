import {
  createContext,
  useContext,
  useState,
  useEffect,
  type ReactNode,
} from "react";
import {
  applyIntensityBackground,
  applyThemeTokens,
  clearManagedThemeVars,
} from "../theme/applyTheme";
import { applyLayerBundle, clearLayerAttributes } from "../theme/applyLayers";
import {
  type ButtonStyleId,
  type BackgroundStyleId,
  PRESET_BY_ID,
  resolvePresetId,
  resolvePresetTokens,
} from "../theme/presets";
import {
  type TypographyPackId,
  type SurfaceStyleId,
  type ButtonVariantId,
  type MotionLevelId,
  type ThemeWidgetToggles,
  type ThemeLayerBundle,
  type TopbarTitleStyleId,
  type TopbarTitleFontId,
  type TopbarTitleSizeId,
  type SidebarStickerFontId,
  type SidebarStickerLayers,
  type SidebarStickerSavedPreset,
  STUDY_DEFAULT_LAYERS,
  PRESET_LAYER_BUNDLES,
  mergeLayerBundle,
  TOPBAR_TITLE_DEFAULTS,
  SIDEBAR_STICKER_DEFAULTS,
  SIDEBAR_STICKER_LAYER_DEFAULTS,
  SIDEBAR_STICKER_FONTS,
  SIDEBAR_STICKER_LAYER_PRESETS,
  clampSidebarStickerScale,
  cloneSidebarStickerLayers,
  coerceSidebarStickerLayers,
  normalizeSidebarStickerLayers,
  isHexColor,
} from "../theme/layers";
import { ContourStickerFilterDefs } from "../components/theme/ContourStickerFilterDefs";

const TOPBAR_TITLE_PREF_VERSION = "5";
const SIDEBAR_STICKER_FONT_IDS = new Set(SIDEBAR_STICKER_FONTS.map((f) => f.id));
const CUSTOM_PRESETS_KEY = "sidebarStickerCustomPresets";

function loadTopbarTitleStyle(): TopbarTitleStyleId {
  const migrated = localStorage.getItem("topbarTitlePrefsV");
  if (migrated !== TOPBAR_TITLE_PREF_VERSION) {
    localStorage.setItem("topbarTitlePrefsV", TOPBAR_TITLE_PREF_VERSION);
    // v5: 3D smooth plate — kill letter-stroke speech-bubble outlines
    localStorage.setItem("topbarTitleStyle", TOPBAR_TITLE_DEFAULTS.style);
    localStorage.setItem("topbarTitleFont", TOPBAR_TITLE_DEFAULTS.font);
    localStorage.setItem("topbarTitleSize", TOPBAR_TITLE_DEFAULTS.size);
  }
  const raw = localStorage.getItem("topbarTitleStyle") as TopbarTitleStyleId | null;
  if (raw === "plain" || raw === "parchment" || raw === "contour") return raw;
  return TOPBAR_TITLE_DEFAULTS.style;
}

function loadTopbarTitleFont(): TopbarTitleFontId {
  const raw = localStorage.getItem("topbarTitleFont") as TopbarTitleFontId | null;
  if (raw === "cursive" || raw === "serif" || raw === "sans") return raw;
  return TOPBAR_TITLE_DEFAULTS.font;
}

function loadTopbarTitleSize(): TopbarTitleSizeId {
  const raw = localStorage.getItem("topbarTitleSize") as TopbarTitleSizeId | null;
  if (raw === "sm" || raw === "md" || raw === "lg") return raw;
  return TOPBAR_TITLE_DEFAULTS.size;
}

function loadSidebarStickerFont(): SidebarStickerFontId {
  const raw = localStorage.getItem("sidebarStickerFont") as SidebarStickerFontId | null;
  if (raw && SIDEBAR_STICKER_FONT_IDS.has(raw)) return raw;
  return SIDEBAR_STICKER_DEFAULTS.font;
}

function loadSidebarStickerScale(): number {
  const raw = localStorage.getItem("sidebarStickerScale");
  if (raw != null && raw !== "") return clampSidebarStickerScale(raw);
  return SIDEBAR_STICKER_DEFAULTS.scale;
}

function loadSidebarStickerCoreFill(): string {
  // One-shot: migrate to rings model + reset stale fill-preset keys.
  if (localStorage.getItem("sidebarStickerContourV") !== "3") {
    const prevLayers = localStorage.getItem("sidebarStickerLayers");
    localStorage.setItem("sidebarStickerContourV", "3");
    if (!localStorage.getItem("sidebarStickerCoreFill")) {
      localStorage.setItem("sidebarStickerCoreFill", SIDEBAR_STICKER_DEFAULTS.coreFill);
    }
    if (!localStorage.getItem("sidebarStickerFont")) {
      localStorage.setItem("sidebarStickerFont", SIDEBAR_STICKER_DEFAULTS.font);
    }
    if (prevLayers) {
      try {
        localStorage.setItem(
          "sidebarStickerLayers",
          JSON.stringify(coerceSidebarStickerLayers(JSON.parse(prevLayers))),
        );
      } catch {
        localStorage.setItem(
          "sidebarStickerLayers",
          JSON.stringify(SIDEBAR_STICKER_DEFAULTS.layers),
        );
      }
    } else {
      localStorage.setItem(
        "sidebarStickerLayers",
        JSON.stringify(SIDEBAR_STICKER_DEFAULTS.layers),
      );
    }
    if (!localStorage.getItem("sidebarStickerScale")) {
      localStorage.setItem("sidebarStickerScale", String(SIDEBAR_STICKER_DEFAULTS.scale));
    }
    localStorage.removeItem("sidebarStickerFill");
    localStorage.removeItem("sidebarStickerOutline");
  }
  const raw = localStorage.getItem("sidebarStickerCoreFill");
  if (isHexColor(raw)) return raw;
  return SIDEBAR_STICKER_DEFAULTS.coreFill;
}

function loadSidebarStickerLayers(): SidebarStickerLayers {
  const raw = loadJson<unknown>("sidebarStickerLayers", null);
  if (!raw) return cloneSidebarStickerLayers(SIDEBAR_STICKER_LAYER_DEFAULTS);
  return coerceSidebarStickerLayers(raw);
}

function loadSidebarStickerCustomPresets(): SidebarStickerSavedPreset[] {
  const raw = loadJson<unknown[]>(CUSTOM_PRESETS_KEY, []);
  if (!Array.isArray(raw)) return [];
  const out: SidebarStickerSavedPreset[] = [];
  for (const item of raw) {
    if (!item || typeof item !== "object") continue;
    const p = item as Partial<SidebarStickerSavedPreset>;
    if (typeof p.id !== "string" || typeof p.label !== "string") continue;
    if (!isHexColor(p.coreFill)) continue;
    if (!p.font || !SIDEBAR_STICKER_FONT_IDS.has(p.font)) continue;
    out.push({
      id: p.id,
      label: p.label.slice(0, 40),
      layers: coerceSidebarStickerLayers(p.layers),
      coreFill: p.coreFill,
      font: p.font,
      scale: clampSidebarStickerScale(p.scale),
      savedAt: typeof p.savedAt === "number" ? p.savedAt : Date.now(),
    });
  }
  return out;
}

interface ThemeContextValue {
  isDarkMode: boolean;
  theme: "light" | "dark";
  toggleTheme: () => void;
  isLoading: boolean;
  accentColor: string;
  radius: string;
  intensity: number;
  buttonStyle: ButtonStyleId;
  backgroundStyle: BackgroundStyleId;
  typographyPack: TypographyPackId;
  surfaceStyle: SurfaceStyleId;
  buttonVariant: ButtonVariantId;
  motionLevel: MotionLevelId;
  widgets: ThemeWidgetToggles;
  topbarTitleStyle: TopbarTitleStyleId;
  topbarTitleFont: TopbarTitleFontId;
  topbarTitleSize: TopbarTitleSizeId;
  sidebarStickerFont: SidebarStickerFontId;
  sidebarStickerScale: number;
  sidebarStickerCoreFill: string;
  sidebarStickerLayers: SidebarStickerLayers;
  sidebarStickerCustomPresets: SidebarStickerSavedPreset[];
  setAccentColor: (color: string) => void;
  setRadius: (radius: string) => void;
  setIntensity: (intensity: number) => void;
  setButtonStyle: (style: ButtonStyleId) => void;
  setBackgroundStyle: (style: BackgroundStyleId) => void;
  setTypographyPack: (pack: TypographyPackId) => void;
  setSurfaceStyle: (style: SurfaceStyleId) => void;
  setButtonVariant: (variant: ButtonVariantId) => void;
  setMotionLevel: (level: MotionLevelId) => void;
  setWidgets: (widgets: ThemeWidgetToggles) => void;
  toggleWidget: (key: keyof ThemeWidgetToggles) => void;
  setTopbarTitleStyle: (style: TopbarTitleStyleId) => void;
  setTopbarTitleFont: (font: TopbarTitleFontId) => void;
  setTopbarTitleSize: (size: TopbarTitleSizeId) => void;
  setSidebarStickerFont: (font: SidebarStickerFontId) => void;
  setSidebarStickerScale: (scale: number) => void;
  setSidebarStickerCoreFill: (hex: string) => void;
  setSidebarStickerLayers: (layers: SidebarStickerLayers) => void;
  applySidebarStickerThemePreset: (presetId: string) => void;
  saveSidebarStickerPreset: (label: string) => string | null;
  deleteSidebarStickerPreset: (presetId: string) => void;
  applyPreset: (presetId: string) => void;
  resetStudyDefaults: () => void;
  isHeroLayersActive: boolean;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error("useTheme must be used within a ThemeProvider");
  }
  return context;
}

const LEGACY_PRIMARY: Record<string, string> = {
  default: "#1a1a2e",
  emerald: "#10b981",
  violet: "#8b5cf6",
  rose: "#f43f5e",
  amber: "#f59e0b",
};

function loadJson<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

function applyLayerBundleToState(
  bundle: ThemeLayerBundle,
  setters: {
    setTypographyPack: (v: TypographyPackId) => void;
    setSurfaceStyle: (v: SurfaceStyleId) => void;
    setButtonVariant: (v: ButtonVariantId) => void;
    setMotionLevel: (v: MotionLevelId) => void;
    setBackgroundStyle: (v: BackgroundStyleId) => void;
    setButtonStyle: (v: ButtonStyleId) => void;
    setWidgets: (v: ThemeWidgetToggles) => void;
  }
) {
  setters.setTypographyPack(bundle.typographyPack);
  setters.setSurfaceStyle(bundle.surfaceStyle);
  setters.setButtonVariant(bundle.buttonVariant);
  setters.setMotionLevel(bundle.motionLevel);
  setters.setBackgroundStyle(bundle.backgroundStyle);
  setters.setButtonStyle(bundle.buttonStyle);
  setters.setWidgets(bundle.widgets);
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [isLoading, setIsLoading] = useState(true);
  const [isDarkMode, setIsDarkMode] = useState(() => {
    const saved = localStorage.getItem("theme");
    return (
      saved === "dark" ||
      (!saved && window.matchMedia("(prefers-color-scheme: dark)").matches)
    );
  });
  const [accentColor, setAccentColor] = useState(() => {
    const saved = localStorage.getItem("accentColor");
    if (saved) return saved;
    return "lemillion-heroic-spotlight";
  });
  const [radius, setRadius] = useState(
    () => localStorage.getItem("radius") || "md"
  );
  const [intensity, setIntensity] = useState(() =>
    parseInt(localStorage.getItem("intensity") || "50", 10)
  );
  const [buttonStyle, setButtonStyle] = useState<ButtonStyleId>(
    () =>
      (localStorage.getItem("buttonStyle") as ButtonStyleId) ||
      STUDY_DEFAULT_LAYERS.buttonStyle
  );
  const [backgroundStyle, setBackgroundStyle] = useState<BackgroundStyleId>(
    () =>
      (localStorage.getItem("backgroundStyle") as BackgroundStyleId) ||
      STUDY_DEFAULT_LAYERS.backgroundStyle
  );
  const [typographyPack, setTypographyPack] = useState<TypographyPackId>(
    () =>
      (localStorage.getItem("typographyPack") as TypographyPackId) ||
      STUDY_DEFAULT_LAYERS.typographyPack
  );
  const [surfaceStyle, setSurfaceStyle] = useState<SurfaceStyleId>(
    () =>
      (localStorage.getItem("surfaceStyle") as SurfaceStyleId) ||
      STUDY_DEFAULT_LAYERS.surfaceStyle
  );
  const [buttonVariant, setButtonVariant] = useState<ButtonVariantId>(
    () =>
      (localStorage.getItem("buttonVariant") as ButtonVariantId) ||
      STUDY_DEFAULT_LAYERS.buttonVariant
  );
  const [motionLevel, setMotionLevel] = useState<MotionLevelId>(
    () =>
      (localStorage.getItem("motionLevel") as MotionLevelId) ||
      STUDY_DEFAULT_LAYERS.motionLevel
  );
  const [widgets, setWidgets] = useState<ThemeWidgetToggles>(() =>
    loadJson("themeWidgets", STUDY_DEFAULT_LAYERS.widgets)
  );
  const [topbarTitleStyle, setTopbarTitleStyle] = useState<TopbarTitleStyleId>(
    loadTopbarTitleStyle
  );
  const [topbarTitleFont, setTopbarTitleFont] = useState<TopbarTitleFontId>(
    loadTopbarTitleFont
  );
  const [topbarTitleSize, setTopbarTitleSize] = useState<TopbarTitleSizeId>(
    loadTopbarTitleSize
  );
  const [sidebarStickerFont, setSidebarStickerFont] = useState<SidebarStickerFontId>(
    loadSidebarStickerFont
  );
  const [sidebarStickerScale, setSidebarStickerScaleState] = useState<number>(
    loadSidebarStickerScale
  );
  const setSidebarStickerScale = (scale: number) => {
    setSidebarStickerScaleState(clampSidebarStickerScale(scale));
  };
  const [sidebarStickerCoreFill, setSidebarStickerCoreFillState] = useState<string>(
    loadSidebarStickerCoreFill
  );
  const setSidebarStickerCoreFill = (hex: string) => {
    if (isHexColor(hex)) setSidebarStickerCoreFillState(hex);
  };
  const [sidebarStickerLayers, setSidebarStickerLayersState] =
    useState<SidebarStickerLayers>(loadSidebarStickerLayers);
  const setSidebarStickerLayers = (layers: SidebarStickerLayers) => {
    setSidebarStickerLayersState(normalizeSidebarStickerLayers(layers));
  };

  const [sidebarStickerCustomPresets, setSidebarStickerCustomPresets] = useState<
    SidebarStickerSavedPreset[]
  >(loadSidebarStickerCustomPresets);

  const applySidebarStickerThemePreset = (presetId: string) => {
    const builtin = SIDEBAR_STICKER_LAYER_PRESETS.find((p) => p.id === presetId);
    if (builtin) {
      setSidebarStickerLayers(cloneSidebarStickerLayers(builtin.layers));
      setSidebarStickerCoreFill(builtin.coreFill);
      if (builtin.font) setSidebarStickerFont(builtin.font);
      if (builtin.scale != null) setSidebarStickerScale(builtin.scale);
      return;
    }
    const custom = sidebarStickerCustomPresets.find((p) => p.id === presetId);
    if (!custom) return;
    setSidebarStickerLayers(cloneSidebarStickerLayers(custom.layers));
    setSidebarStickerCoreFill(custom.coreFill);
    setSidebarStickerFont(custom.font);
    setSidebarStickerScale(custom.scale);
  };

  const saveSidebarStickerPreset = (label: string): string | null => {
    const trimmed = label.trim().slice(0, 40);
    if (!trimmed) return null;
    const id = `custom-${Date.now().toString(36)}`;
    const next: SidebarStickerSavedPreset = {
      id,
      label: trimmed,
      layers: cloneSidebarStickerLayers(sidebarStickerLayers),
      coreFill: sidebarStickerCoreFill,
      font: sidebarStickerFont,
      scale: sidebarStickerScale,
      savedAt: Date.now(),
    };
    setSidebarStickerCustomPresets((prev) => {
      const merged = [next, ...prev].slice(0, 24);
      localStorage.setItem(CUSTOM_PRESETS_KEY, JSON.stringify(merged));
      return merged;
    });
    return id;
  };

  const deleteSidebarStickerPreset = (presetId: string) => {
    setSidebarStickerCustomPresets((prev) => {
      const merged = prev.filter((p) => p.id !== presetId);
      localStorage.setItem(CUSTOM_PRESETS_KEY, JSON.stringify(merged));
      return merged;
    });
  };

  const applyPreset = (presetId: string) => {
    const preset = PRESET_BY_ID[presetId];
    if (preset?.preferDark) setIsDarkMode(true);
    if (presetId === "lemillion-pro" && preset && !preset.preferDark) {
      setIsDarkMode(false);
    }
    setAccentColor(presetId);

    const bundle = mergeLayerBundle(PRESET_LAYER_BUNDLES[presetId]);
    applyLayerBundleToState(bundle, {
      setTypographyPack,
      setSurfaceStyle,
      setButtonVariant,
      setMotionLevel,
      setBackgroundStyle,
      setButtonStyle,
      setWidgets,
    });
  };

  const resetStudyDefaults = () => {
    setAccentColor("default");
    setRadius("md");
    setIntensity(50);
    setTopbarTitleStyle(TOPBAR_TITLE_DEFAULTS.style);
    setTopbarTitleFont(TOPBAR_TITLE_DEFAULTS.font);
    setTopbarTitleSize(TOPBAR_TITLE_DEFAULTS.size);
    setSidebarStickerFont(SIDEBAR_STICKER_DEFAULTS.font);
    setSidebarStickerScale(SIDEBAR_STICKER_DEFAULTS.scale);
    setSidebarStickerCoreFill(SIDEBAR_STICKER_DEFAULTS.coreFill);
    setSidebarStickerLayers(cloneSidebarStickerLayers(SIDEBAR_STICKER_DEFAULTS.layers));
    applyLayerBundleToState(STUDY_DEFAULT_LAYERS, {
      setTypographyPack,
      setSurfaceStyle,
      setButtonVariant,
      setMotionLevel,
      setBackgroundStyle,
      setButtonStyle,
      setWidgets,
    });
  };

  const toggleWidget = (key: keyof ThemeWidgetToggles) => {
    setWidgets((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const layers: ThemeLayerBundle = {
    typographyPack,
    surfaceStyle,
    buttonVariant,
    backgroundStyle,
    buttonStyle,
    motionLevel,
    widgets,
  };

  const isHeroLayersActive =
    typographyPack !== "study" ||
    surfaceStyle !== "gloss" ||
    buttonVariant !== "default" ||
    motionLevel !== "off" ||
    widgets.lemillionAssistant ||
    widgets.heroProgress;

  useEffect(() => {
    localStorage.setItem("theme", isDarkMode ? "dark" : "light");
    localStorage.setItem("accentColor", accentColor);
    localStorage.setItem("radius", radius);
    localStorage.setItem("intensity", intensity.toString());
    localStorage.setItem("buttonStyle", buttonStyle);
    localStorage.setItem("backgroundStyle", backgroundStyle);
    localStorage.setItem("typographyPack", typographyPack);
    localStorage.setItem("surfaceStyle", surfaceStyle);
    localStorage.setItem("buttonVariant", buttonVariant);
    localStorage.setItem("motionLevel", motionLevel);
    localStorage.setItem("themeWidgets", JSON.stringify(widgets));
    localStorage.setItem("topbarTitleStyle", topbarTitleStyle);
    localStorage.setItem("topbarTitleFont", topbarTitleFont);
    localStorage.setItem("topbarTitleSize", topbarTitleSize);
    localStorage.setItem("sidebarStickerFont", sidebarStickerFont);
    localStorage.setItem("sidebarStickerScale", String(sidebarStickerScale));
    localStorage.setItem("sidebarStickerCoreFill", sidebarStickerCoreFill);
    localStorage.setItem("sidebarStickerLayers", JSON.stringify(sidebarStickerLayers));

    const root = document.documentElement;
    const presetId = resolvePresetId(accentColor);

    clearManagedThemeVars(root);
    clearLayerAttributes(root);

    root.setAttribute("data-accent-preset", presetId ?? "custom");
    root.setAttribute("data-button-style", buttonStyle);
    root.setAttribute("data-bg-style", backgroundStyle);
    root.setAttribute("data-color-scheme", isDarkMode ? "dark" : "light");
    root.setAttribute("data-topbar-title-style", topbarTitleStyle);
    root.setAttribute("data-topbar-title-font", topbarTitleFont);
    root.setAttribute("data-topbar-title-size", topbarTitleSize);
    root.setAttribute("data-sidebar-sticker-font", sidebarStickerFont);
    root.style.setProperty("--sidebar-sticker-scale", String(sidebarStickerScale));
    root.style.setProperty("--sidebar-sticker-core", sidebarStickerCoreFill);
    root.setAttribute("data-sidebar-sticker-outline", "true");
    root.classList.toggle("dark", isDarkMode);

    applyLayerBundle(root, layers);

    if (presetId) {
      const tokens = resolvePresetTokens(presetId, isDarkMode);
      applyThemeTokens(root, tokens, isDarkMode);
      if (presetId === "default") {
        applyIntensityBackground(root, isDarkMode, intensity);
      }
    } else if (accentColor.startsWith("#")) {
      applyThemeTokens(
        root,
        { primary: accentColor, background: isDarkMode ? "#050505" : "#fafbfc" },
        isDarkMode
      );
      applyIntensityBackground(root, isDarkMode, intensity);
    } else {
      const primary =
        LEGACY_PRIMARY[accentColor] ??
        (isDarkMode ? "#f5f5f7" : LEGACY_PRIMARY.default);
      applyThemeTokens(
        root,
        { primary, background: isDarkMode ? "#050505" : "#fafbfc" },
        isDarkMode
      );
      applyIntensityBackground(root, isDarkMode, intensity);
    }

    const radiusMap: Record<string, string> = {
      sm: "0.375rem",
      md: "0.625rem",
      lg: "1rem",
      xl: "1.5rem",
    };
    const baseRadius = radiusMap[radius] || radiusMap.md;
    root.style.setProperty("--radius", baseRadius);

    const btnRadiusByStyle: Record<ButtonStyleId, string> = {
      default: baseRadius,
      gloss: baseRadius,
      pill: "9999px",
      comic: "0.25rem",
      sharp: "0.125rem",
    };
    root.style.setProperty("--btn-radius-override", btnRadiusByStyle[buttonStyle]);

    setIsLoading(false);
  }, [
    isDarkMode,
    accentColor,
    radius,
    intensity,
    buttonStyle,
    backgroundStyle,
    typographyPack,
    surfaceStyle,
    buttonVariant,
    motionLevel,
    widgets,
    topbarTitleStyle,
    topbarTitleFont,
    topbarTitleSize,
    sidebarStickerFont,
    sidebarStickerScale,
    sidebarStickerCoreFill,
    sidebarStickerLayers,
  ]);

  const toggleTheme = () => setIsDarkMode((v) => !v);

  return (
    <ThemeContext.Provider
      value={{
        isDarkMode,
        theme: isDarkMode ? "dark" : "light",
        toggleTheme,
        isLoading,
        accentColor,
        radius,
        intensity,
        buttonStyle,
        backgroundStyle,
        typographyPack,
        surfaceStyle,
        buttonVariant,
        motionLevel,
        widgets,
        topbarTitleStyle,
        topbarTitleFont,
        topbarTitleSize,
        sidebarStickerFont,
        sidebarStickerScale,
        sidebarStickerCoreFill,
        sidebarStickerLayers,
        sidebarStickerCustomPresets,
        setAccentColor,
        setRadius,
        setIntensity,
        setButtonStyle,
        setBackgroundStyle,
        setTypographyPack,
        setSurfaceStyle,
        setButtonVariant,
        setMotionLevel,
        setWidgets,
        toggleWidget,
        setTopbarTitleStyle,
        setTopbarTitleFont,
        setTopbarTitleSize,
        setSidebarStickerFont,
        setSidebarStickerScale,
        setSidebarStickerCoreFill,
        setSidebarStickerLayers,
        applySidebarStickerThemePreset,
        saveSidebarStickerPreset,
        deleteSidebarStickerPreset,
        applyPreset,
        resetStudyDefaults,
        isHeroLayersActive,
      }}
    >
      <ContourStickerFilterDefs />
      {children}
    </ThemeContext.Provider>
  );
}
