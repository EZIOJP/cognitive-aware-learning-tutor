import type { StudyLoopTag } from "../../../api/globalQuizClient";

export type KindFilter = "all" | "math" | "lecture" | "vocab";

export const KIND_FILTERS: { id: KindFilter; label: string }[] = [
  { id: "all", label: "All" },
  { id: "math", label: "Math" },
  { id: "lecture", label: "Lecture" },
  { id: "vocab", label: "Vocab" },
];

/** Map StudyLoopTag.kind / group / id heuristics → board kind. */
export function tagBoardKind(tag: StudyLoopTag): Exclude<KindFilter, "all"> {
  const group = String(tag.group || "").toLowerCase();
  if (group === "math" || group === "lecture" || group === "vocab") {
    return group;
  }
  const kind = String(tag.kind || "").toLowerCase();
  if (kind === "vocab_group" || kind.startsWith("vocab")) return "vocab";
  const id = String(tag.id || "").toUpperCase();
  if (id.startsWith("MT")) return "math";
  if (/^L\d+-T/i.test(id)) return "lecture";
  return "lecture";
}

export function filterTagsByKind(tags: StudyLoopTag[], kind: KindFilter): StudyLoopTag[] {
  if (kind === "all") return tags;
  return tags.filter((t) => tagBoardKind(t) === kind);
}

export function kindCount(tags: StudyLoopTag[], kind: KindFilter): number {
  return filterTagsByKind(tags, kind).length;
}
