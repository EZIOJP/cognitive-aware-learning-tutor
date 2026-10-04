/** Shared page titles for Focus sidebar / Study top bar. */

export const PAGE_TITLES: Record<string, string> = {
  "/": "Study Hub",
  "/admin": "Admin",
  "/profile": "Profile",
  "/settings": "Settings",
  "/settings/ai": "AI Control",
  "/settings/theme": "Theme",
  "/settings/plugins": "Plugins",
  "/settings/features": "Feature Studio",
  "/math-tutor": "Math Tutor",
  "/math-tutor/reports": "Math Reports",
  "/math-tutor/recognize-test": "Math Recognize",
  "/math-tutor/train": "Math Train",
  "/gre-vocab": "GRE Vocabulary",
  "/gre-vocab/add-words": "Add Words",
  "/gre-vocab/read": "Vocab Read",
  "/gre-vocab/cycle": "Vocab Cycle",
  "/lecture-notes": "Lecture Notes",
  "/review": "Study Loop",
  "/study-room": "Study Room",
  "/journal": "Journal",
  "/productivity": "Home",
  "/productivity/focus": "Settings",
  "/bible": "Bible",
  "/life-tracker": "Life Tracker",
  "/nutrition": "Nutrition",
  "/focus/calibrate": "Focus Calibrate",
};

export const PAGE_SUBTITLES: Record<string, string> = {
  "/": "Your daily learning home",
  "/gre-vocab": "Adaptive vocabulary practice",
  "/math-tutor": "Topics, drills, and progress",
  "/productivity": "Mode, progress, and SoftLand blocks",
  "/productivity/focus": "Gate control and native enforcer",
  "/bible": "Chapter reading for SoftLand unlock",
  "/lecture-notes": "Capture and study lectures",
  "/review": "Vocab · lecture · math · decks · FSRS",
  "/settings": "Appearance, AI, and plugins",
  "/settings/theme": "Preview and switch look",
  "/journal": "Reflect and track mood",
  "/life-tracker": "Habits and life score",
  "/nutrition": "Macros and meals",
};

export function matchLongestPrefix(pathname: string, table: Record<string, string>): string | null {
  let best: string | null = null;
  let bestLen = -1;
  for (const [path, label] of Object.entries(table)) {
    if (path === "/") {
      if (pathname === "/" && path.length > bestLen) {
        best = label;
        bestLen = path.length;
      }
      continue;
    }
    if ((pathname === path || pathname.startsWith(`${path}/`)) && path.length > bestLen) {
      best = label;
      bestLen = path.length;
    }
  }
  return best;
}

function humanizeSegment(segment: string): string {
  return segment
    .split("-")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function resolvePageTitle(
  pathname: string,
  navItems: { to: string; label: string }[] = [],
): string {
  const fromMap = matchLongestPrefix(pathname, PAGE_TITLES);
  if (fromMap) return fromMap;

  let bestLabel: string | null = null;
  let bestLen = -1;
  for (const item of navItems) {
    const path = item.to.startsWith("/") ? item.to : `/${item.to}`;
    if (path === "/") continue;
    if ((pathname === path || pathname.startsWith(`${path}/`)) && path.length > bestLen) {
      bestLabel = item.label;
      bestLen = path.length;
    }
  }
  if (bestLabel) return bestLabel;

  const segments = pathname.split("/").filter(Boolean);
  if (segments.length === 0) return "Study Hub";
  return humanizeSegment(segments[segments.length - 1] ?? "Study Companion");
}

/** Focus productivity tabs override the generic /productivity → Home map. */
export function resolveFocusShellTitle(pathname: string, tab: string | null): string {
  if (pathname === "/productivity" || pathname.startsWith("/productivity/")) {
    if (tab === "calendar") return "Calendar";
    if (tab === "plan") return "Planner";
    if (tab === "analytics") return "Analytics";
    if (tab === "settings") return "Settings";
    return "Home";
  }
  if (pathname.startsWith("/bible")) return "Bible";
  if (pathname.startsWith("/journal")) return "Journal";
  if (pathname.startsWith("/profile")) return "Profile";
  return resolvePageTitle(pathname);
}
