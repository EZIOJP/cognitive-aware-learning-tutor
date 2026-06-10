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
