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
  STUDY_DEFAULT_LAYERS,
  PRESET_LAYER_BUNDLES,
  mergeLayerBundle,
} from "../theme/layers";

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

    const root = document.documentElement;
    const presetId = resolvePresetId(accentColor);

    clearManagedThemeVars(root);
    clearLayerAttributes(root);

    root.setAttribute("data-accent-preset", presetId ?? "custom");
    root.setAttribute("data-button-style", buttonStyle);
    root.setAttribute("data-bg-style", backgroundStyle);
    root.setAttribute("data-color-scheme", isDarkMode ? "dark" : "light");
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
        applyPreset,
        resetStudyDefaults,
        isHeroLayersActive,
      }}
    >
      {children}
    </ThemeContext.Provider>
  );
}
