/** Composable theme layers — Stitch hero toolkit options */

export type TypographyPackId = "study" | "hero" | "motivator";
export type SurfaceStyleId = "gloss" | "comic" | "flat";
export type ButtonVariantId =
  | "default"
  | "comic"
  | "chamfer"
  | "dashed"
  | "skew"
  | "shiny";
export type MotionLevelId = "off" | "subtle" | "hero";

export interface ThemeWidgetToggles {
  lemillionAssistant: boolean;
  heroProgress: boolean;
}

export interface ThemeLayerBundle {
  typographyPack: TypographyPackId;
  surfaceStyle: SurfaceStyleId;
  buttonVariant: ButtonVariantId;
  backgroundStyle: import("./presets").BackgroundStyleId;
  buttonStyle: import("./presets").ButtonStyleId;
  motionLevel: MotionLevelId;
  widgets: ThemeWidgetToggles;
}

export const STUDY_DEFAULT_LAYERS: ThemeLayerBundle = {
  typographyPack: "study",
  surfaceStyle: "gloss",
  buttonVariant: "default",
  backgroundStyle: "minimal",
  buttonStyle: "default",
  motionLevel: "off",
  widgets: { lemillionAssistant: false, heroProgress: false },
};

export const PRESET_LAYER_BUNDLES: Record<string, Partial<ThemeLayerBundle>> = {
  default: { ...STUDY_DEFAULT_LAYERS },
  emerald: { ...STUDY_DEFAULT_LAYERS },
  violet: { ...STUDY_DEFAULT_LAYERS },
  rose: { ...STUDY_DEFAULT_LAYERS },
  amber: { ...STUDY_DEFAULT_LAYERS },
  "midnight-amber": {
    typographyPack: "study",
    surfaceStyle: "gloss",
    buttonVariant: "default",
    backgroundStyle: "gradient",
    buttonStyle: "gloss",
    motionLevel: "off",
    widgets: { lemillionAssistant: false, heroProgress: false },
  },
  "oceanic-aurora": {
    typographyPack: "study",
    surfaceStyle: "gloss",
    buttonVariant: "default",
    backgroundStyle: "gradient",
    buttonStyle: "default",
    motionLevel: "off",
    widgets: { lemillionAssistant: false, heroProgress: false },
  },
  "lemillion-heroic-spotlight": {
    typographyPack: "study",
    surfaceStyle: "gloss",
    buttonVariant: "default",
    backgroundStyle: "minimal",
    buttonStyle: "default",
    motionLevel: "off",
    widgets: { lemillionAssistant: false, heroProgress: false },
  },
  "lemillion-dynamic-grit": {
    typographyPack: "hero",
    surfaceStyle: "comic",
    buttonVariant: "comic",
    backgroundStyle: "gradient",
    buttonStyle: "comic",
    motionLevel: "subtle",
    widgets: { lemillionAssistant: false, heroProgress: true },
  },
  "lemillion-hero-toolkit": {
    typographyPack: "hero",
    surfaceStyle: "comic",
    buttonVariant: "chamfer",
    backgroundStyle: "halftone",
    buttonStyle: "comic",
    motionLevel: "subtle",
    widgets: { lemillionAssistant: false, heroProgress: true },
  },
  "lemillion-high-velocity": {
    typographyPack: "hero",
    surfaceStyle: "comic",
    buttonVariant: "shiny",
    backgroundStyle: "speed-lines",
    buttonStyle: "comic",
    motionLevel: "hero",
    widgets: { lemillionAssistant: false, heroProgress: true },
  },
  "lemillion-pro": {
    typographyPack: "motivator",
    surfaceStyle: "gloss",
    buttonVariant: "default",
    backgroundStyle: "gradient",
    buttonStyle: "default",
    motionLevel: "hero",
    widgets: { lemillionAssistant: true, heroProgress: false },
  },
};

export function mergeLayerBundle(partial?: Partial<ThemeLayerBundle>): ThemeLayerBundle {
  return {
    ...STUDY_DEFAULT_LAYERS,
    ...partial,
    widgets: {
      ...STUDY_DEFAULT_LAYERS.widgets,
      ...partial?.widgets,
    },
  };
}

export const TYPOGRAPHY_PACKS: {
  id: TypographyPackId;
  label: string;
  hint?: string;
}[] = [
  { id: "study", label: "Study", hint: "App default fonts" },
  { id: "hero", label: "Hero", hint: "Anton + Space Grotesk + Work Sans" },
  { id: "motivator", label: "Motivator", hint: "Montserrat + Inter" },
];

export const SURFACE_STYLES: {
  id: SurfaceStyleId;
  label: string;
  hint?: string;
}[] = [
  { id: "gloss", label: "Gloss", hint: "Glass panels (default)" },
  { id: "comic", label: "Comic", hint: "Bold border + shadow" },
  { id: "flat", label: "Flat", hint: "No gloss blur" },
];

export const BUTTON_VARIANTS: {
  id: ButtonVariantId;
  label: string;
  hint?: string;
}[] = [
  { id: "default", label: "Default" },
  { id: "comic", label: "Comic power" },
  { id: "chamfer", label: "Chamfer" },
  { id: "dashed", label: "Dashed tactical" },
  { id: "skew", label: "Skew flow" },
  { id: "shiny", label: "Shiny armor" },
];

export const MOTION_LEVELS: {
  id: MotionLevelId;
  label: string;
  hint?: string;
}[] = [
  { id: "off", label: "Off", hint: "Best for focus" },
  { id: "subtle", label: "Subtle", hint: "Hover only" },
  { id: "hero", label: "Hero", hint: "Shine + permeation" },
];

/** Top bar page-title chrome (Theme settings — independent of preset packs). */
export type TopbarTitleStyleId = "plain" | "parchment" | "contour";
export type TopbarTitleFontId = "cursive" | "serif" | "sans";
export type TopbarTitleSizeId = "sm" | "md" | "lg";

export const TOPBAR_TITLE_STYLES: {
  id: TopbarTitleStyleId;
  label: string;
  hint?: string;
}[] = [
  { id: "parchment", label: "Hairline", hint: "Editorial type with a short primary rule that grows on hover" },
  { id: "contour", label: "Rule", hint: "Full-width primary rule under the title" },
  { id: "plain", label: "Bare", hint: "Title and subtitle only — no accent" },
];

export const TOPBAR_TITLE_FONTS: {
  id: TopbarTitleFontId;
  label: string;
  hint?: string;
}[] = [
  { id: "cursive", label: "Cursive", hint: "Caveat script" },
  { id: "serif", label: "Serif", hint: "Playfair — editorial" },
  { id: "sans", label: "Sans", hint: "System UI" },
];

export const TOPBAR_TITLE_SIZES: {
  id: TopbarTitleSizeId;
  label: string;
  hint?: string;
}[] = [
  { id: "sm", label: "Small" },
  { id: "md", label: "Medium" },
  { id: "lg", label: "Large" },
];

export const TOPBAR_TITLE_DEFAULTS = {
  style: "parchment" as TopbarTitleStyleId,
  font: "cursive" as TopbarTitleFontId,
  size: "lg" as TopbarTitleSizeId,
};

/** Focus sidebar page-title — True Contour SVG die-cut (feMorphology). */
export type SidebarStickerFontId =
  | "great-vibes"
  | "allura"
  | "alex-brush"
  | "pinyon"
  | "tangerine"
  | "italianno"
  | "monsieur"
  | "mrs-saint"
  | "imperial"
  | "bonheur"
  | "euphoria"
  | "arizonia"
  | "bilbo"
  | "whisper"
  | "parisienne"
  | "sacramento"
  | "dancing"
  | "satisfy"
  | "yellowtail"
  | "kaushan"
  | "pacifico"
  | "oooh-baby"
  | "caveat"
  | "homemade";

export type SidebarStickerFontGroup = "calligraphy" | "cursive" | "brush";

export const SIDEBAR_STICKER_FONTS: {
  id: SidebarStickerFontId;
  label: string;
  hint?: string;
  group: SidebarStickerFontGroup;
  css: string;
}[] = [
  { id: "great-vibes", label: "Great Vibes", hint: "Formal wedding calligraphy", group: "calligraphy", css: '"Great Vibes", cursive' },
  { id: "monsieur", label: "Monsieur La Doulaise", hint: "Ultra ornate flourishes", group: "calligraphy", css: '"Monsieur La Doulaise", "Great Vibes", cursive' },
  { id: "mrs-saint", label: "Mrs Saint Delafield", hint: "Fine pointed pen", group: "calligraphy", css: '"Mrs Saint Delafield", "Great Vibes", cursive' },
  { id: "imperial", label: "Imperial Script", hint: "High-contrast formal script", group: "calligraphy", css: '"Imperial Script", "Great Vibes", cursive' },
  { id: "bonheur", label: "Bonheur Royale", hint: "Royal copperplate", group: "calligraphy", css: '"Bonheur Royale", "Great Vibes", cursive' },
  { id: "euphoria", label: "Euphoria Script", hint: "Lush italic calligraphy", group: "calligraphy", css: '"Euphoria Script", "Great Vibes", cursive' },
  { id: "allura", label: "Allura", hint: "Elegant flowing script", group: "calligraphy", css: '"Allura", "Great Vibes", cursive' },
  { id: "alex-brush", label: "Alex Brush", hint: "Refined pen calligraphy", group: "calligraphy", css: '"Alex Brush", "Great Vibes", cursive' },
  { id: "pinyon", label: "Pinyon Script", hint: "Delicate formal script", group: "calligraphy", css: '"Pinyon Script", "Great Vibes", cursive' },
  { id: "tangerine", label: "Tangerine", hint: "Light ornate calligraphy", group: "calligraphy", css: '"Tangerine", "Great Vibes", cursive' },
  { id: "italianno", label: "Italianno", hint: "Romantic Italian script", group: "calligraphy", css: '"Italianno", "Great Vibes", cursive' },
  { id: "arizonia", label: "Arizonia", hint: "Dramatic italic flourish", group: "calligraphy", css: '"Arizonia", "Great Vibes", cursive' },
  { id: "bilbo", label: "Bilbo Swash Caps", hint: "Swash capital italics", group: "calligraphy", css: '"Bilbo Swash Caps", "Great Vibes", cursive' },
  { id: "whisper", label: "Whisper", hint: "Airy thin calligraphy", group: "calligraphy", css: '"Whisper", "Great Vibes", cursive' },
  { id: "parisienne", label: "Parisienne", hint: "Parisian elegance", group: "cursive", css: '"Parisienne", "Great Vibes", cursive' },
  { id: "sacramento", label: "Sacramento", hint: "Soft connected cursive", group: "cursive", css: '"Sacramento", "Oooh Baby", cursive' },
  { id: "dancing", label: "Dancing Script", hint: "Lively cursive", group: "cursive", css: '"Dancing Script", cursive' },
  { id: "satisfy", label: "Satisfy", hint: "Smooth italic script", group: "cursive", css: '"Satisfy", cursive' },
  { id: "yellowtail", label: "Yellowtail", hint: "Bold brush italic", group: "cursive", css: '"Yellowtail", cursive' },
  { id: "kaushan", label: "Kaushan Script", hint: "Painted italic script", group: "cursive", css: '"Kaushan Script", cursive' },
  { id: "pacifico", label: "Pacifico", hint: "Casual brush script", group: "brush", css: '"Pacifico", cursive' },
  { id: "oooh-baby", label: "Oooh Baby", hint: "Modern brush", group: "brush", css: '"Oooh Baby", cursive' },
  { id: "caveat", label: "Caveat", hint: "Friendly handwritten", group: "brush", css: '"Caveat", cursive' },
  { id: "homemade", label: "Homemade Apple", hint: "Handwritten italic", group: "brush", css: '"Homemade Apple", cursive' },
];

/** One contour ring — radius in tool px, painted outside the glyph. */
export type SidebarStickerRing = {
  radius: number;
  color: string;
};

/** Rings ordered inner → outer (ascending radius). */
export type SidebarStickerLayers = {
  rings: SidebarStickerRing[];
};

export const SIDEBAR_STICKER_RINGS_MIN = 1;
export const SIDEBAR_STICKER_RINGS_MAX = 6;
export const SIDEBAR_STICKER_RADIUS_MIN = 2;
export const SIDEBAR_STICKER_RADIUS_MAX = 120;

export const SIDEBAR_STICKER_LAYER_DEFAULTS: SidebarStickerLayers = {
  rings: [
    { radius: 15, color: "#ffffff" },
    { radius: 28, color: "#e10600" },
    { radius: 38, color: "#ffffff" },
  ],
};

export type SidebarStickerBuiltinPreset = {
  id: string;
  label: string;
  hint?: string;
  layers: SidebarStickerLayers;
  coreFill: string;
  font?: SidebarStickerFontId;
  scale?: number;
};

export type SidebarStickerSavedPreset = {
  id: string;
  label: string;
  layers: SidebarStickerLayers;
  coreFill: string;
  font: SidebarStickerFontId;
  scale: number;
  savedAt: number;
};

function ringsOf(
  entries: [number, string][],
): SidebarStickerLayers {
  return {
    rings: entries.map(([radius, color]) => ({ radius, color })),
  };
}

export const SIDEBAR_STICKER_LAYER_PRESETS: SidebarStickerBuiltinPreset[] = [
  {
    id: "classic-white",
    label: "Classic White",
    hint: "White / red / white",
    layers: ringsOf([
      [15, "#ffffff"],
      [28, "#e10600"],
      [38, "#ffffff"],
    ]),
    coreFill: "#111827",
  },
  {
    id: "soft-ivory",
    label: "Soft Ivory",
    hint: "Cream rings, gold mid",
    layers: ringsOf([
      [12, "#fffaf0"],
      [22, "#c9a227"],
      [32, "#fff8e7"],
    ]),
    coreFill: "#111827",
  },
  {
    id: "noir-gold",
    label: "Noir Gold",
    hint: "Gold contour sheet",
    layers: ringsOf([
      [10, "#f5e6a8"],
      [20, "#b8860b"],
      [34, "#fff8dc"],
    ]),
    coreFill: "#111827",
  },
  {
    id: "blush",
    label: "Blush",
    hint: "Soft rose rings",
    layers: ringsOf([
      [14, "#fff5f7"],
      [24, "#e11d48"],
      [36, "#ffe4e9"],
    ]),
    coreFill: "#111827",
  },
  {
    id: "minimal",
    label: "Minimal",
    hint: "Thin elegant edge",
    layers: ringsOf([
      [6, "#ffffff"],
      [10, "#d4d4d8"],
      [16, "#ffffff"],
    ]),
    coreFill: "#111827",
  },
  {
    id: "bold",
    label: "Bold die-cut",
    hint: "Heavy contour sheet",
    layers: ringsOf([
      [18, "#ffffff"],
      [32, "#e10600"],
      [48, "#ffffff"],
    ]),
    coreFill: "#111827",
  },
  {
    id: "single-ivory",
    label: "Single Ivory",
    hint: "One soft halo",
    layers: ringsOf([[22, "#fff8e7"]]),
    coreFill: "#111827",
  },
  {
    id: "quad-ink",
    label: "Quad Ink",
    hint: "Four stacked rings",
    layers: ringsOf([
      [8, "#ffffff"],
      [16, "#111827"],
      [26, "#ffffff"],
      [40, "#e10600"],
    ]),
    coreFill: "#111827",
  },
];

/** Title size as percent of default rail weight — freer growth. */
export const SIDEBAR_STICKER_SCALE_MIN = 50;
export const SIDEBAR_STICKER_SCALE_MAX = 220;
export const SIDEBAR_STICKER_SCALE_DEFAULT = 100;

export function clampSidebarStickerScale(n: unknown): number {
  const v = typeof n === "number" ? n : Number(n);
  if (!Number.isFinite(v)) return SIDEBAR_STICKER_SCALE_DEFAULT;
  return Math.min(
    SIDEBAR_STICKER_SCALE_MAX,
    Math.max(SIDEBAR_STICKER_SCALE_MIN, Math.round(v)),
  );
}

export function clampSidebarStickerLayer(n: unknown, fallback: number): number {
  const v = typeof n === "number" ? n : Number(n);
  if (!Number.isFinite(v)) return fallback;
  return Math.min(
    SIDEBAR_STICKER_RADIUS_MAX,
    Math.max(SIDEBAR_STICKER_RADIUS_MIN, Math.round(v)),
  );
}

export function isHexColor(v: unknown): v is string {
  return typeof v === "string" && /^#[0-9a-fA-F]{6}$/.test(v);
}

export function cloneSidebarStickerLayers(
  layers: SidebarStickerLayers,
): SidebarStickerLayers {
  return {
    rings: layers.rings.map((r) => ({ radius: r.radius, color: r.color })),
  };
}

/** Sort ascending + enforce strictly increasing radii. */
export function normalizeSidebarStickerLayers(
  layers: SidebarStickerLayers,
): SidebarStickerLayers {
  const sorted = [...layers.rings]
    .map((r, i) => ({
      radius: clampSidebarStickerLayer(r.radius, 8 + i * 10),
      color: isHexColor(r.color) ? r.color : "#ffffff",
    }))
    .sort((a, b) => a.radius - b.radius)
    .slice(0, SIDEBAR_STICKER_RINGS_MAX);

  if (sorted.length === 0) {
    return cloneSidebarStickerLayers(SIDEBAR_STICKER_LAYER_DEFAULTS);
  }

  for (let i = 1; i < sorted.length; i++) {
    if (sorted[i].radius <= sorted[i - 1].radius) {
      sorted[i] = {
        ...sorted[i],
        radius: Math.min(
          SIDEBAR_STICKER_RADIUS_MAX,
          sorted[i - 1].radius + 2,
        ),
      };
    }
  }
  return { rings: sorted };
}

/** Migrate legacy {layer1,color1…} or rings payloads. */
export function coerceSidebarStickerLayers(raw: unknown): SidebarStickerLayers {
  if (!raw || typeof raw !== "object") {
    return cloneSidebarStickerLayers(SIDEBAR_STICKER_LAYER_DEFAULTS);
  }
  const obj = raw as Record<string, unknown>;
  if (Array.isArray(obj.rings)) {
    return normalizeSidebarStickerLayers({
      rings: obj.rings.map((r) => {
        const ring = r as Partial<SidebarStickerRing>;
        return {
          radius: clampSidebarStickerLayer(ring.radius, 15),
          color: isHexColor(ring.color) ? ring.color : "#ffffff",
        };
      }),
    });
  }
  // Legacy fixed-3 shape
  if (
    "layer1" in obj ||
    "layer2" in obj ||
    "layer3" in obj
  ) {
    return normalizeSidebarStickerLayers({
      rings: [
        {
          radius: clampSidebarStickerLayer(obj.layer1, 15),
          color: isHexColor(obj.color1) ? obj.color1 : "#ffffff",
        },
        {
          radius: clampSidebarStickerLayer(obj.layer2, 28),
          color: isHexColor(obj.color2) ? obj.color2 : "#e10600",
        },
        {
          radius: clampSidebarStickerLayer(obj.layer3, 38),
          color: isHexColor(obj.color3) ? obj.color3 : "#ffffff",
        },
      ],
    });
  }
  return cloneSidebarStickerLayers(SIDEBAR_STICKER_LAYER_DEFAULTS);
}

export function addSidebarStickerRing(
  layers: SidebarStickerLayers,
  color = "#ffffff",
): SidebarStickerLayers {
  if (layers.rings.length >= SIDEBAR_STICKER_RINGS_MAX) {
    return normalizeSidebarStickerLayers(layers);
  }
  const last = layers.rings[layers.rings.length - 1];
  const nextRadius = Math.min(
    SIDEBAR_STICKER_RADIUS_MAX,
    (last?.radius ?? 12) + 12,
  );
  return normalizeSidebarStickerLayers({
    rings: [...layers.rings, { radius: nextRadius, color }],
  });
}

export function removeSidebarStickerRing(
  layers: SidebarStickerLayers,
  index: number,
): SidebarStickerLayers {
  if (layers.rings.length <= SIDEBAR_STICKER_RINGS_MIN) {
    return normalizeSidebarStickerLayers(layers);
  }
  if (index < 0 || index >= layers.rings.length) {
    return normalizeSidebarStickerLayers(layers);
  }
  return normalizeSidebarStickerLayers({
    rings: layers.rings.filter((_, i) => i !== index),
  });
}

export function updateSidebarStickerRing(
  layers: SidebarStickerLayers,
  index: number,
  patch: Partial<SidebarStickerRing>,
): SidebarStickerLayers {
  if (index < 0 || index >= layers.rings.length) {
    return normalizeSidebarStickerLayers(layers);
  }
  const rings = layers.rings.map((r, i) => {
    if (i !== index) return r;
    return {
      radius:
        patch.radius !== undefined
          ? clampSidebarStickerLayer(patch.radius, r.radius)
          : r.radius,
      color: isHexColor(patch.color) ? patch.color : r.color,
    };
  });
  return normalizeSidebarStickerLayers({ rings });
}

export const SIDEBAR_STICKER_DEFAULTS = {
  font: "great-vibes" as SidebarStickerFontId,
  scale: SIDEBAR_STICKER_SCALE_DEFAULT,
  coreFill: "#111827",
  layers: cloneSidebarStickerLayers(SIDEBAR_STICKER_LAYER_DEFAULTS),
  presetId: "classic-white",
};
