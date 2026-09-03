/** CAT QA pillar multipliers (appendix mid-weights). Metadata only — not a second orchestrator. */
export const PILLAR_WEIGHTS: Record<string, number> = {
  arithmetic: 1.35,
  algebra: 1.25,
  geometry: 1.175,
  mensuration: 1.175,
  "number systems": 1.175,
  number: 1.175,
  modern: 1.125,
  combinatorics: 1.125,
  probability: 1.125,
};

export function resolvePillarWeight(tag: {
  id?: string;
  label?: string;
  pillar_weight?: number;
  note_paths?: string[];
}): number {
  if (typeof tag.pillar_weight === "number" && Number.isFinite(tag.pillar_weight)) {
    return tag.pillar_weight;
  }
  const hay = [tag.id, tag.label, ...(tag.note_paths || [])]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  for (const [key, weight] of Object.entries(PILLAR_WEIGHTS)) {
    if (hay.includes(key)) return weight;
  }
  return 1;
}

export function tagSortScore(tag: {
  due_count?: number;
  pillar_weight?: number;
  id?: string;
  label?: string;
  note_paths?: string[];
}): number {
  return (tag.due_count || 0) * (tag.pillar_weight ?? resolvePillarWeight(tag));
}
