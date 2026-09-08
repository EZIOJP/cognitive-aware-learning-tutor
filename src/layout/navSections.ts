/** Shared nav section taxonomy for sidebar + Focus (feature organization). */

export type NavSectionId = "study" | "focus" | "life" | "system";

export const NAV_SECTION_ORDER: NavSectionId[] = ["study", "focus", "life", "system"];

export const NAV_SECTION_LABELS: Record<NavSectionId, string> = {
  study: "Study",
  focus: "Focus",
  life: "Life",
  system: "System",
};

/** Preferred order of destinations within / across sections. */
export const NAV_PATH_ORDER: string[] = [
  "/lecture-notes",
  "/review",
  "/journal",
  "/gre-vocab",
  "/math-tutor",
  "/study-room",
  "/productivity/focus",
  "/productivity",
  "/bible",
  "/life-tracker",
  "/nutrition",
  "/",
  "/settings",
  "/admin",
];

const PATH_SECTION: Record<string, NavSectionId> = {
  "/": "system",
  "/lecture-notes": "study",
  "/review": "study",
  "/journal": "study",
  "/gre-vocab": "study",
  "/math-tutor": "study",
  "/study-room": "study",
  "/productivity": "focus",
  "/productivity/focus": "focus",
  "/bible": "life",
  "/life-tracker": "life",
  "/nutrition": "life",
  "/settings": "system",
  "/admin": "system",
};

export function resolveNavSection(to: string, explicit?: NavSectionId | null): NavSectionId {
  if (explicit) return explicit;
  if (PATH_SECTION[to]) return PATH_SECTION[to];
  if (to.startsWith("/productivity")) return "focus";
  if (to.startsWith("/math")) return "study";
  if (to.startsWith("/life")) return "life";
  if (to.startsWith("/nutrition")) return "life";
  if (to.startsWith("/bible")) return "life";
  if (to.startsWith("/gre") || to.startsWith("/lecture") || to.startsWith("/review") || to.startsWith("/journal") || to.startsWith("/study")) {
    return "study";
  }
  return "system";
}

export function navPathRank(to: string): number {
  const i = NAV_PATH_ORDER.indexOf(to);
  return i >= 0 ? i : 500 + to.length;
}
