import { useParams } from "react-router";
import { ReadMode } from "../../features/vocab/components/read/ReadMode";
import type { ReadListMode } from "../../features/vocab/store/vocabStore";

const MODE_MAP: Record<string, ReadListMode> = {
  all: "all",
  "low-mastery": "low",
  due: "due",
  struggling: "struggling",
  learning: "learning",
  practicing: "practicing",
  mastered: "mastered",
};

export function VocabReadPage() {
  const { mode: modeParam } = useParams<{ mode?: string }>();
  const listMode = (modeParam && MODE_MAP[modeParam]) || "all";

  return (
    <div className="h-full min-h-0 flex flex-col">
      <ReadMode listMode={listMode} markOnNext={listMode !== "mastered"} />
    </div>
  );
}
