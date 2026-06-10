/** Stitch-derived theme presets — tokens from docs/stitch-export */

export type ThemePresetGroup = "basic" | "life-clock" | "lemillion" | "study-hub";
export type ThemeEnergy = "calm" | "moderate" | "intense";

export type ButtonStyleId = "default" | "gloss" | "pill" | "comic" | "sharp";
export type BackgroundStyleId =
  | "solid"
  | "gradient"
  | "spotlight"
  | "halftone"
  | "speed-lines"
  | "minimal";

export interface ThemeTokens {
  primary: string;
  primaryForeground?: string;
  secondary?: string;
  secondaryForeground?: string;
  background: string;
  foreground?: string;
  card?: string;
  cardForeground?: string;
  muted?: string;
  mutedForeground?: string;
  accent?: string;
  accentForeground?: string;
  border?: string;
}

export interface ThemePreset {
  id: string;
  label: string;
  group: ThemePresetGroup;
  hint?: string;
  preview?: string;
  energy?: ThemeEnergy;
  /** Force dark mode when selected (Lemillion hero themes) */
  preferDark?: boolean;
  tokens: { dark: ThemeTokens; light?: ThemeTokens };
}

export const BUTTON_STYLES: { id: ButtonStyleId; label: string; hint?: string }[] = [
  { id: "default", label: "Default", hint: "Standard rounded buttons" },
  { id: "gloss", label: "Gloss", hint: "Soft glass highlight" },
  { id: "pill", label: "Pill", hint: "Fully rounded" },
  { id: "comic", label: "Comic", hint: "Bold border + offset shadow (hero)" },
  { id: "sharp", label: "Sharp", hint: "Square corners" },
];

export const BACKGROUND_STYLES: {
  id: BackgroundStyleId;
  label: string;
  hint?: string;
}[] = [
  { id: "minimal", label: "Minimal", hint: "Flat — least distracting" },
  { id: "solid", label: "Solid", hint: "Single color" },
  { id: "gradient", label: "Gradient", hint: "Soft radial glow" },
  { id: "spotlight", label: "Spotlight", hint: "Hero vignette (navy)" },
  { id: "halftone", label: "Halftone", hint: "Comic dot texture" },
  { id: "speed-lines", label: "Speed lines", hint: "Action diagonal lines" },
];

export const BASIC_ACCENTS: ThemePreset[] = [
  {
    id: "default",
    label: "Default",
    group: "basic",
    energy: "calm",
    tokens: {
      dark: {
        primary: "#f5f5f7",
        background: "#050505",
        card: "#0c0c0c",
        foreground: "#f5f5f7",
      },
      light: {
        primary: "#1a1a2e",
        background: "#fafbfc",
        card: "#ffffff",
        foreground: "#0a0a0b",
      },
    },
  },
  {
    id: "emerald",
    label: "Emerald",
    group: "basic",
    tokens: {
      dark: { primary: "#10b981", background: "#050505", card: "#0c0c0c" },
      light: { primary: "#10b981", background: "#fafbfc", card: "#ffffff" },
    },
  },
  {
    id: "violet",
    label: "Violet",
    group: "basic",
    tokens: {
      dark: { primary: "#8b5cf6", background: "#050505", card: "#0c0c0c" },
      light: { primary: "#8b5cf6", background: "#fafbfc", card: "#ffffff" },
    },
  },
  {
    id: "rose",
    label: "Rose",
    group: "basic",
    tokens: {
      dark: { primary: "#f43f5e", background: "#050505", card: "#0c0c0c" },
      light: { primary: "#f43f5e", background: "#fafbfc", card: "#ffffff" },
    },
  },
  {
    id: "amber",
    label: "Amber",
    group: "basic",
    tokens: {
      dark: { primary: "#f59e0b", background: "#050505", card: "#0c0c0c" },
      light: { primary: "#f59e0b", background: "#fafbfc", card: "#ffffff" },
    },
  },
];

export const LIFE_CLOCK_PRESETS: ThemePreset[] = [
  {
    id: "midnight-amber",
    label: "Midnight Amber",
    group: "life-clock",
    hint: "Stitch Life Clock",
    preview: "/theme-previews/midnight-amber.jpg",
    energy: "moderate",
    preferDark: true,
    tokens: {
      dark: {
        primary: "#f59e0b",
        primaryForeground: "#451a03",
        secondary: "#fbbf24",
        background: "#121212",
        card: "#1a1a1a",
        foreground: "#f5f5f7",
        muted: "#262626",
        accent: "#78350f",
        border: "rgba(255,255,255,0.08)",
      },
    },
  },
  {
    id: "oceanic-aurora",
    label: "Oceanic Aurora",
    group: "life-clock",
    hint: "Stitch teal clock",
    preview: "/theme-previews/oceanic-aurora.jpg",
    energy: "calm",
    preferDark: true,
    tokens: {
      dark: {
        primary: "#06b6d4",
        primaryForeground: "#083344",
        secondary: "#2dd4bf",
        background: "#0a191e",
        card: "#112a32",
        foreground: "#e2f1f1",
        muted: "#15333d",
        accent: "#164e63",
        border: "rgba(255,255,255,0.08)",
      },
    },
  },
];

/** Lemillion / hero variants — from Stitch Spiderman + Phasing Motivator projects */
export const LEMILLION_PRESETS: ThemePreset[] = [
  {
    id: "lemillion-heroic-spotlight",
    label: "Heroic Spotlight",
    group: "lemillion",
    hint: "Deep navy — calmest hero theme",
    preview: "/theme-previews/lemillion-heroic-spotlight.jpg",
    energy: "calm",
    preferDark: true,
    tokens: {
      dark: {
        primary: "#ffb4ab",
        primaryForeground: "#410002",
        secondary: "#a1c9ff",
        secondaryForeground: "#001c37",
        background: "#001833",
        card: "#001c3d",
        foreground: "#e2e2e2",
        muted: "#1a1c1c",
        accent: "#00234a",
        border: "rgba(174,136,131,0.35)",
      },
    },
  },
  {
    id: "lemillion-dynamic-grit",
    label: "Dynamic Grit",
    group: "lemillion",
    hint: "Dark grit — moderate energy",
    preview: "/theme-previews/lemillion-dynamic-grit.jpg",
    energy: "moderate",
    preferDark: true,
    tokens: {
      dark: {
        primary: "#ffb4ab",
        secondary: "#a1c9ff",
        background: "#121414",
        card: "#1a1c1c",
        foreground: "#e2e2e2",
        muted: "#282a2b",
        accent: "#333535",
        border: "rgba(255,255,255,0.08)",
      },
    },
  },
  {
    id: "lemillion-hero-toolkit",
    label: "Hero Toolkit",
    group: "lemillion",
    hint: "Design tokens + comic accents",
    preview: "/theme-previews/lemillion-hero-toolkit.jpg",
    energy: "moderate",
    preferDark: true,
    tokens: {
      dark: {
        primary: "#e61c23",
        primaryForeground: "#ffffff",
        secondary: "#00599b",
        secondaryForeground: "#d2e4ff",
        background: "#121414",
        card: "#282a2b",
        foreground: "#e2e2e2",
        muted: "#333535",
        accent: "#00599b",
        border: "rgba(0,0,0,0.4)",
      },
    },
  },
  {
    id: "lemillion-high-velocity",
    label: "High-Velocity",
    group: "lemillion",
    hint: "Gold + red motion — intense",
    preview: "/theme-previews/lemillion-high-velocity.jpg",
    energy: "intense",
    preferDark: true,
    tokens: {
      dark: {
        primary: "#FFD700",
        primaryForeground: "#410002",
        secondary: "#E61C23",
        background: "#121414",
        card: "#1a1c1c",
        foreground: "#e2e2e2",
        muted: "#282a2b",
        accent: "#93000c",
        border: "rgba(255,215,0,0.2)",
      },
    },
  },
  {
    id: "lemillion-pro",
    label: "Pro Edition",
    group: "lemillion",
    hint: "Light gold motivator — flashy",
    preview: "/theme-previews/lemillion-pro.jpg",
    energy: "intense",
    tokens: {
      light: {
        primary: "#705d00",
        primaryForeground: "#ffffff",
        secondary: "#b52424",
        secondaryForeground: "#ffffff",
        background: "#f8f9fa",
        card: "#ffffff",
        foreground: "#191c1d",
        muted: "#edeeef",
        accent: "#ffd700",
        border: "rgba(126,119,95,0.25)",
      },
      dark: {
        primary: "#ffe16d",
        secondary: "#ff5a52",
        background: "#191c1d",
        card: "#2e3132",
        foreground: "#f0f1f2",
      },
    },
  },
];

export const ALL_THEME_PRESETS: ThemePreset[] = [
  ...BASIC_ACCENTS,
  ...LIFE_CLOCK_PRESETS,
  ...LEMILLION_PRESETS,
];

export const PRESET_BY_ID = Object.fromEntries(
  ALL_THEME_PRESETS.map((p) => [p.id, p])
) as Record<string, ThemePreset>;

export function resolvePresetId(accentColor: string): string | null {
  if (accentColor.startsWith("#")) return null;
  return PRESET_BY_ID[accentColor] ? accentColor : null;
}

/** Safe light palette when a preset only defines dark tokens — preserves accent hue */
export function deriveLightTokensFromDark(dark: ThemeTokens): ThemeTokens {
  return {
    background: "#f8f9fa",
    foreground: "#191c1d",
    card: "#ffffff",
    cardForeground: "#191c1d",
    primary: dark.primary,
    primaryForeground: dark.primaryForeground ?? "#ffffff",
    secondary: dark.secondary ?? "#f0f2f5",
    secondaryForeground: dark.secondaryForeground ?? "#191c1d",
    muted: "#edeeef",
    mutedForeground: "#5c5f6b",
    accent: dark.accent ?? "#f4f6f9",
    accentForeground: dark.accentForeground ?? "#191c1d",
    border: "rgba(0,0,0,0.1)",
  };
}

export function getTokensForPreset(
  presetId: string,
  isDark: boolean
): ThemeTokens | null {
  const preset = PRESET_BY_ID[presetId];
  if (!preset) return null;
  if (isDark) return preset.tokens.dark;
  return preset.tokens.light ?? null;
}

/** Resolves preset tokens for the active scheme; derives light from dark when needed */
export function resolvePresetTokens(
  presetId: string,
  isDark: boolean
): ThemeTokens | null {
  const preset = PRESET_BY_ID[presetId];
  if (!preset) return null;
  const raw = getTokensForPreset(presetId, isDark);
  if (raw) return raw;
  if (!isDark) return deriveLightTokensFromDark(preset.tokens.dark);
  return preset.tokens.dark;
}
