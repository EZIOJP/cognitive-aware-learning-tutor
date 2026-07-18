export type LifeClockSkinId = "classic" | "sectograph" | "omnitrix" | "ribbon";

export const LIFE_CLOCK_SKINS: { id: LifeClockSkinId; label: string }[] = [
  { id: "classic", label: "Classic" },
  { id: "sectograph", label: "Sectograph" },
  { id: "omnitrix", label: "Omnitrix" },
  { id: "ribbon", label: "Ribbon" },
];

const STORAGE_KEY = "calt:life-clock-skin";

export function loadLifeClockSkin(): LifeClockSkinId {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw === "classic" || raw === "sectograph" || raw === "omnitrix" || raw === "ribbon") {
      return raw;
    }
    if (raw === "dna") return "ribbon";
  } catch {
    /* ignore */
  }
  return "classic";
}

export function saveLifeClockSkin(skin: LifeClockSkinId): void {
  try {
    localStorage.setItem(STORAGE_KEY, skin);
  } catch {
    /* ignore */
  }
}

export function nextLifeClockSkin(current: LifeClockSkinId): LifeClockSkinId {
  const i = LIFE_CLOCK_SKINS.findIndex((s) => s.id === current);
  return LIFE_CLOCK_SKINS[(i + 1) % LIFE_CLOCK_SKINS.length]!.id;
}
