import type { DueReviewItem } from "../types";

/** True if a due review item intersects the active tag set. */
export function dueIntersectsActive(item: DueReviewItem, activeIds: string[]): boolean {
  if (!activeIds.length) return true;
  const want = new Set(activeIds.map((x) => x.toLowerCase()));
  const topic = String(item.topic || "").trim().toLowerCase();
  if (topic && want.has(topic)) return true;

  const payload = item.payload || {};
  const candidates: string[] = [];
  for (const key of ["note_topic_id", "tag", "topic_id", "topic"]) {
    const v = payload[key];
    if (typeof v === "string" && v.trim()) candidates.push(v.trim().toLowerCase());
  }
  const tags = payload.tags;
  if (Array.isArray(tags)) {
    for (const t of tags) {
      if (typeof t === "string" && t.trim()) candidates.push(t.trim().toLowerCase());
    }
  }
  if (candidates.some((c) => want.has(c))) return true;

  const label = String(item.label || "").toLowerCase();
  for (const id of want) {
    if (id && label.includes(id)) return true;
  }
  return false;
}
