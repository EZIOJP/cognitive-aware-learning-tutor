import type { ThemeLayerBundle } from "./layers";

const LAYER_ATTRS = [
  "data-typography-pack",
  "data-surface-style",
  "data-button-variant",
  "data-motion-level",
] as const;

export function clearLayerAttributes(root: HTMLElement) {
  for (const attr of LAYER_ATTRS) {
    root.removeAttribute(attr);
  }
}

export function applyLayerBundle(root: HTMLElement, layers: ThemeLayerBundle) {
  root.setAttribute("data-typography-pack", layers.typographyPack);
  root.setAttribute("data-surface-style", layers.surfaceStyle);
  root.setAttribute("data-button-variant", layers.buttonVariant);
  root.setAttribute("data-motion-level", layers.motionLevel);
}
