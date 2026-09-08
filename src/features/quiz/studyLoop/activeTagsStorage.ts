const ACTIVE_KEY = "calt.studyLoop.activeTags";
const PREFS_KEY = "calt.studyLoop.prefs";

export const ACTIVE_TAG_CAP = 4;

export type StudyLoopPrefs = {
  showFsrsUnderActive: boolean;
  showProgressRails: boolean;
  speedFluencyUi: boolean;
};

const DEFAULT_PREFS: StudyLoopPrefs = {
  showFsrsUnderActive: true,
  showProgressRails: false,
  speedFluencyUi: true,
};

function safeParseJson(raw: string | null): unknown {
  if (!raw) return null;
  try {
    return JSON.parse(raw) as unknown;
  } catch {
    return null;
  }
}

export function loadActiveTagIds(): string[] {
  const parsed = safeParseJson(
    typeof localStorage !== "undefined" ? localStorage.getItem(ACTIVE_KEY) : null
  );
  if (!Array.isArray(parsed)) return [];
  return parsed
    .map((x) => String(x || "").trim())
    .filter(Boolean)
    .slice(0, ACTIVE_TAG_CAP);
}

export function saveActiveTagIds(ids: string[]): void {
  const next = [...new Set(ids.map((x) => String(x || "").trim()).filter(Boolean))].slice(
    0,
    ACTIVE_TAG_CAP
  );
  localStorage.setItem(ACTIVE_KEY, JSON.stringify(next));
}

export function loadStudyLoopPrefs(): StudyLoopPrefs {
  const parsed = safeParseJson(
    typeof localStorage !== "undefined" ? localStorage.getItem(PREFS_KEY) : null
  );
  if (!parsed || typeof parsed !== "object") return { ...DEFAULT_PREFS };
  const o = parsed as Record<string, unknown>;
  return {
    showFsrsUnderActive:
      typeof o.showFsrsUnderActive === "boolean"
        ? o.showFsrsUnderActive
        : DEFAULT_PREFS.showFsrsUnderActive,
    showProgressRails:
      typeof o.showProgressRails === "boolean"
        ? o.showProgressRails
        : DEFAULT_PREFS.showProgressRails,
    speedFluencyUi:
      typeof o.speedFluencyUi === "boolean" ? o.speedFluencyUi : DEFAULT_PREFS.speedFluencyUi,
  };
}

export function saveStudyLoopPrefs(prefs: StudyLoopPrefs): void {
  localStorage.setItem(PREFS_KEY, JSON.stringify(prefs));
}
