import type { CognitiveLoad } from "../types";

/** Fixed-width labels so UI does not resize when load changes */
export const COGNITIVE_LOAD_SHORT: Record<CognitiveLoad, string> = {
  low: "LOW",
  medium: "MED",
  high: "HIGH",
};

export const COGNITIVE_LOAD_BADGE: Record<CognitiveLoad, string> = {
  low: "LOW",
  medium: "MEDIUM",
  high: "HIGH",
};

export const COGNITIVE_LOAD_PERCENT: Record<CognitiveLoad, string> = {
  low: "30%",
  medium: "65%",
  high: "92%",
};
