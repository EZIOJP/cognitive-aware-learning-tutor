import type { StudyLoopTag } from "../../../api/globalQuizClient";

/** Top-level Learn folders — Math Core first (matches backend learn_folders). */
export const LEARN_FOLDER_ORDER = [
  "math-core",
  "math",
  "numpy",
  "pandas",
  "lecture",
  "vocab",
] as const;

export type LearnFolderId = (typeof LEARN_FOLDER_ORDER)[number] | "other";

export const LEARN_FOLDER_LABELS: Record<string, string> = {
  "math-core": "Math Core",
  math: "Math",
  numpy: "NumPy",
  pandas: "Pandas",
  lecture: "Lecture",
  vocab: "Vocab",
  other: "Other",
};

export function tagFolder(tag: StudyLoopTag): LearnFolderId {
  const f = String(tag.folder || "").trim();
  if (f && (LEARN_FOLDER_ORDER as readonly string[]).includes(f)) {
    return f as LearnFolderId;
  }
  if (f === "other") return "other";
  const id = String(tag.id || "").toUpperCase();
  if (id.startsWith("MT0-") || id.startsWith("MT1-")) return "math-core";
  if (id.startsWith("MT")) return "math";
  if (/^L[23]-T/i.test(id)) return "numpy";
  if (/^L[45]-T/i.test(id)) return "pandas";
  if (/^L\d+-T/i.test(id)) return "lecture";
  if (id.startsWith("VOCAB") || String(tag.id || "").toLowerCase().startsWith("vocab.")) {
    return "vocab";
  }
  return "other";
}

export type FolderGroup = {
  id: LearnFolderId;
  label: string;
  tags: StudyLoopTag[];
};

export function groupTagsByFolder(tags: StudyLoopTag[]): FolderGroup[] {
  const buckets = new Map<string, StudyLoopTag[]>();
  for (const t of tags) {
    const f = tagFolder(t);
    const list = buckets.get(f) || [];
    list.push(t);
    buckets.set(f, list);
  }
  const ordered: FolderGroup[] = [];
  for (const id of LEARN_FOLDER_ORDER) {
    const list = buckets.get(id) || [];
    if (!list.length && id === "vocab") {
      // still show empty vocab slot only if we have other folders — skip empty
      continue;
    }
    if (!list.length) continue;
    ordered.push({
      id,
      label: LEARN_FOLDER_LABELS[id] || id,
      tags: list,
    });
  }
  const other = buckets.get("other") || [];
  if (other.length) {
    ordered.push({ id: "other", label: "Other", tags: other });
  }
  return ordered;
}
