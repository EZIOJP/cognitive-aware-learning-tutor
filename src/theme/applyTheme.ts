import type { ThemeTokens } from "./presets";

/** CSS variables managed by ThemeProvider — cleared before each apply */
export const MANAGED_THEME_VARS = [
  "--background",
  "--foreground",
  "--card",
  "--card-foreground",
  "--popover",
  "--popover-foreground",
  "--primary",
  "--primary-foreground",
  "--secondary",
  "--secondary-foreground",
  "--muted",
  "--muted-foreground",
  "--accent",
  "--accent-foreground",
  "--border",
  "--ring",
  "--input",
  "--input-background",
  "--gloss-bg",
  "--gloss-surface",
  "--gloss-border",
  "--gloss-shadow",
  "--gloss-highlight",
  "--sidebar",
  "--sidebar-foreground",
  "--sidebar-primary",
  "--sidebar-primary-foreground",
  "--sidebar-accent",
  "--sidebar-accent-foreground",
  "--sidebar-border",
  "--sidebar-ring",
] as const;

const DARK_BASE: ThemeTokens = {
  background: "#050505",
  foreground: "#f5f5f7",
  card: "#0c0c0c",
  cardForeground: "#f5f5f7",
  primary: "#f5f5f7",
  primaryForeground: "#0a0a0a",
  secondary: "#1a1a1a",
  secondaryForeground: "#f5f5f7",
  muted: "#1a1a1a",
  mutedForeground: "#a1a1aa",
  accent: "#1f1f1f",
  accentForeground: "#f5f5f7",
  border: "rgba(255,255,255,0.1)",
};

const LIGHT_BASE: ThemeTokens = {
  background: "#fafbfc",
  foreground: "#0a0a0b",
  card: "#ffffff",
  cardForeground: "#0a0a0b",
  primary: "#1a1a2e",
  primaryForeground: "#ffffff",
  secondary: "#f0f2f5",
  secondaryForeground: "#1a1a2e",
  muted: "#eef0f4",
  mutedForeground: "#5c5f6b",
  accent: "#f4f6f9",
  accentForeground: "#1a1a2e",
  border: "rgba(0,0,0,0.1)",
};

export function clearManagedThemeVars(root: HTMLElement) {
  for (const key of MANAGED_THEME_VARS) {
    root.style.removeProperty(key);
  }
}

function parseHex(hex: string): [number, number, number] | null {
  const h = hex.replace("#", "").trim();
  if (h.length === 3) {
    return [
      parseInt(h[0] + h[0], 16),
      parseInt(h[1] + h[1], 16),
      parseInt(h[2] + h[2], 16),
    ];
  }
  if (h.length === 6) {
    return [
      parseInt(h.slice(0, 2), 16),
      parseInt(h.slice(2, 4), 16),
      parseInt(h.slice(4, 6), 16),
    ];
  }
  return null;
}

function relativeLuminance(color: string): number {
  const rgb = parseHex(color);
  if (!rgb) return 0.5;
  const [r, g, b] = rgb.map((c) => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function contrastRatio(fg: string, bg: string): number {
  const l1 = relativeLuminance(fg);
  const l2 = relativeLuminance(bg);
  const lighter = Math.max(l1, l2);
  const darker = Math.min(l1, l2);
  return (lighter + 0.05) / (darker + 0.05);
}

function pickForegroundForBackground(bg: string, isDark: boolean): string {
  const white = "#ffffff";
  const black = "#0a0a0a";
  const onWhite = contrastRatio(black, bg);
  const onBlack = contrastRatio(white, bg);
  if (onWhite >= onBlack) return black;
  return white;
}

type ForegroundPair = {
  bgKey: keyof ThemeTokens;
  fgKey: keyof ThemeTokens;
};

const SEMANTIC_PAIRS: ForegroundPair[] = [
  { bgKey: "primary", fgKey: "primaryForeground" },
  { bgKey: "secondary", fgKey: "secondaryForeground" },
  { bgKey: "card", fgKey: "cardForeground" },
  { bgKey: "accent", fgKey: "accentForeground" },
  { bgKey: "muted", fgKey: "mutedForeground" },
];

/** Ensures readable text/background pairs before tokens hit the DOM */
export function ensureSemanticPairs(
  tokens: ThemeTokens,
  isDark: boolean
): ThemeTokens {
  const out = { ...tokens };

  if (!out.foreground && out.background) {
    out.foreground = pickForegroundForBackground(out.background, isDark);
  }

  for (const { bgKey, fgKey } of SEMANTIC_PAIRS) {
    const bg = out[bgKey];
    if (!bg || typeof bg !== "string") continue;
    let fg = out[fgKey];
    if (!fg || typeof fg !== "string") {
      fg = pickForegroundForBackground(bg, isDark);
      (out as Record<string, string>)[fgKey] = fg;
      continue;
    }
    if (contrastRatio(fg, bg) < 4.5) {
      (out as Record<string, string>)[fgKey] = pickForegroundForBackground(bg, isDark);
    }
  }

  return out;
}

function mergeTokens(partial: ThemeTokens | null, isDark: boolean): ThemeTokens {
  const base = isDark ? DARK_BASE : LIGHT_BASE;
  if (!partial) return { ...base };
  const merged = {
    ...base,
    ...partial,
    card: partial.card ?? base.card,
    cardForeground: partial.cardForeground ?? partial.foreground ?? base.cardForeground,
    mutedForeground: partial.mutedForeground ?? base.mutedForeground,
    secondary: partial.secondary ?? base.secondary,
    secondaryForeground:
      partial.secondaryForeground ?? base.secondaryForeground,
    accent: partial.accent ?? base.accent,
    accentForeground: partial.accentForeground ?? base.accentForeground,
    border: partial.border ?? base.border,
  };
  return ensureSemanticPairs(merged, isDark);
}

export function applyThemeTokens(root: HTMLElement, partial: ThemeTokens | null, isDark: boolean) {
  const t = mergeTokens(partial, isDark);
  const card = t.card!;
  const bg = t.background;
  const fg = t.foreground!;
  const muted = t.muted ?? (isDark ? "#1a1a1a" : "#eef0f4");
  const primary = t.primary;
  const ring = t.border?.includes("rgb") ? primary : primary;

  const set = (key: string, val: string) => root.style.setProperty(key, val);

  set("--background", bg);
  set("--foreground", fg);
  set("--card", card);
  set("--card-foreground", t.cardForeground!);
  set("--popover", card);
  set("--popover-foreground", t.cardForeground!);
  set("--primary", primary);
  set("--primary-foreground", t.primaryForeground ?? (isDark ? "#0a0a0a" : "#ffffff"));
  set("--secondary", t.secondary!);
  set("--secondary-foreground", t.secondaryForeground!);
  set("--muted", muted);
  set("--muted-foreground", t.mutedForeground!);
  set("--accent", t.accent!);
  set("--accent-foreground", t.accentForeground!);
  set("--border", t.border!);
  set("--ring", ring);
  set("--input", isDark ? muted : "transparent");
  set("--input-background", isDark ? muted : "#f3f3f5");

  set("--gloss-bg", bg);
  set("--gloss-surface", `color-mix(in srgb, ${card} 92%, transparent)`);
  set("--gloss-border", isDark ? "rgba(255,255,255,0.08)" : "rgba(0,0,0,0.06)");
  set(
    "--gloss-shadow",
    isDark
      ? "0 4px 32px rgba(0,0,0,0.5), 0 0 1px rgba(255,255,255,0.06)"
      : "0 4px 24px rgba(0,0,0,0.06), 0 1px 3px rgba(0,0,0,0.04)"
  );
  set(
    "--gloss-highlight",
    isDark
      ? `linear-gradient(180deg, color-mix(in srgb, ${card} 98%, white) 0%, color-mix(in srgb, ${bg} 95%, black) 100%)`
      : "linear-gradient(180deg, rgba(255,255,255,0.95) 0%, rgba(248,250,252,0.88) 100%)"
  );

  set("--sidebar", card);
  set("--sidebar-foreground", fg);
  set("--sidebar-primary", primary);
  set("--sidebar-primary-foreground", t.primaryForeground ?? "#ffffff");
  set("--sidebar-accent", muted);
  set("--sidebar-accent-foreground", fg);
  set("--sidebar-border", t.border!);
  set("--sidebar-ring", ring);
}

export function applyIntensityBackground(
  root: HTMLElement,
  isDark: boolean,
  intensity: number
) {
  if (isDark) {
    const l = 30 - intensity * 0.3;
    root.style.setProperty("--background", `hsl(240 10% ${l}%)`);
    root.style.setProperty("--gloss-bg", `hsl(240 10% ${l}%)`);
  } else {
    const l = 90 + intensity * 0.1;
    root.style.setProperty("--background", `hsl(0 0% ${l}%)`);
    root.style.setProperty("--gloss-bg", `hsl(0 0% ${l}%)`);
  }
}
