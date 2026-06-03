import {
  createContext,
  useContext,
  useState,
  useEffect,
  type ReactNode,
} from "react";

interface ThemeContextValue {
  isDarkMode: boolean;
  theme: "light" | "dark";
  toggleTheme: () => void;
  isLoading: boolean;
  accentColor: string; // hex or preset name
  radius: string; // e.g., "sm", "md", "lg"
  intensity: number; // 0 to 100
  setAccentColor: (color: string) => void;
  setRadius: (radius: string) => void;
  setIntensity: (intensity: number) => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error("useTheme must be used within a ThemeProvider");
  }
  return context;
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
    const prefersDark =
      localStorage.getItem("theme") === "dark" ||
      (!localStorage.getItem("theme") &&
        window.matchMedia("(prefers-color-scheme: dark)").matches);
    return prefersDark ? "midnight-amber" : "default";
  });
  const [radius, setRadius] = useState(() => {
    return localStorage.getItem("radius") || "md";
  });
  const [intensity, setIntensity] = useState(() => {
    return parseInt(localStorage.getItem("intensity") || "50", 10);
  });

  // Persist theme, accent and radius
  useEffect(() => {
    localStorage.setItem("theme", isDarkMode ? "dark" : "light");
    localStorage.setItem("accentColor", accentColor);
    localStorage.setItem("radius", radius);
    localStorage.setItem("intensity", intensity.toString());

    // Inject CSS variables for accent and radius
    const root = document.documentElement;
    // Map accentColor to primary color -- you can expand mapping as needed
    const accentMap: Record<string, string> = {
      default: isDarkMode ? "#f5f5f7" : "#1a1a2e",
      emerald: "#10b981",
      violet: "#8b5cf6",
      rose: "#f43f5e",
      amber: "#f59e0b",
      "midnight-amber": "#f59e0b",
      "oceanic-aurora": "#06b6d4",
    };

    const isMidnightAmber = accentColor === "midnight-amber";
    const isOceanic = accentColor === "oceanic-aurora";
    root.setAttribute(
      "data-accent-preset",
      isMidnightAmber ? "midnight-amber" : isOceanic ? "oceanic-aurora" : accentColor
    );

    const primaryColor = accentColor.startsWith("#")
      ? accentColor
      : accentMap[accentColor] || accentMap.default;
    root.style.setProperty("--primary", primaryColor);
    if (isMidnightAmber && isDarkMode) {
      root.style.setProperty("--secondary", "#fbbf24");
    }
    if (isOceanic && isDarkMode) {
      root.style.setProperty("--secondary", "#2dd4bf");
    }

    if (isMidnightAmber && isDarkMode) {
      root.style.setProperty("--background", "#121212");
      root.style.setProperty("--card", "#1a1a1a");
    } else if (isOceanic && isDarkMode) {
      root.style.setProperty("--background", "#0a191e");
      root.style.setProperty("--card", "#112a32");
    } else if (isDarkMode) {
      // dark mode: lower intensity = lighter gray, higher = pitch black
      // base dark mode bg might be hsl(240, 10%, 15%)
      // intensity 100 -> l=0%, intensity 0 -> l=30%
      const l = 30 - (intensity * 0.3);
      root.style.setProperty("--background", `hsl(240 10% ${l}%)`);
    } else {
      // light mode: lower intensity = darker gray/off-white, higher = pure white
      // intensity 100 -> l=100%, intensity 0 -> l=90%
      const l = 90 + (intensity * 0.1);
      root.style.setProperty("--background", `hsl(0 0% ${l}%)`);
    }

    // radius mapping (assumes base radius defined in theme.css)
    const radiusMap: Record<string, string> = {
      sm: "0.375rem",
      md: "0.625rem",
      lg: "1rem",
      xl: "1.5rem",
    };
    root.style.setProperty("--radius", radiusMap[radius] || radiusMap["md"]);
    // Update dark/light attribute
    root.setAttribute("data-color-scheme", isDarkMode ? "dark" : "light");
    root.classList.toggle("dark", isDarkMode);
    setIsLoading(false);
  }, [isDarkMode, accentColor, radius, intensity]);

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
        setAccentColor,
        setRadius,
        setIntensity,
      }}
    >
      {children}
    </ThemeContext.Provider>
  );
}


