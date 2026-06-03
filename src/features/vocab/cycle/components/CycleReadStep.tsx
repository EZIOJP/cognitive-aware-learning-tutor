import { useCallback, useEffect, useState } from "react";
import { ChevronLeft, ChevronRight, BookOpen } from "lucide-react";
import { Button } from "../../../../app/components/ui/button";
import { Progress } from "../../../../app/components/ui/progress";
import type { WordWithProgress } from "../../types";
import { WordCard } from "../../components/read/WordCard";

interface CycleReadStepProps {
  words: WordWithProgress[];
  groupNumber: number;
  isLowMastery?: boolean;
  onComplete: (words: WordWithProgress[]) => void;
  onBack: () => void;
}

export function CycleReadStep({
  words,
  groupNumber,
  isLowMastery = false,
  onComplete,
  onBack,
}: CycleReadStepProps) {
  const [index, setIndex] = useState(0);
  const total = words.length;
  const current = words[index];
  const pct = total > 0 ? ((index + 1) / total) * 100 : 0;

  const go = useCallback(
    (dir: number) => {
      if (total === 0) return;
      const next = index + dir;
      if (next >= total) {
        onComplete(words);
        return;
      }
      if (next < 0) return;
      setIndex(next);
    },
    [index, total, words, onComplete]
  );

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight" || e.key === " ") {
        e.preventDefault();
        go(1);
      } else if (e.key === "ArrowLeft") {
        e.preventDefault();
        go(-1);
      } else if (e.key === "Escape") {
        onBack();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [go, onBack]);

  if (total === 0) {
    return (
      <div className="gloss-panel rounded-2xl p-8 text-center">
        <p className="text-muted-foreground mb-4">No words in this group.</p>
        <Button onClick={onBack}>Back to dashboard</Button>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col gap-3 min-h-0">
      <div className="gloss-panel rounded-2xl p-3 shrink-0 space-y-2">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 min-w-0">
            <BookOpen className="w-4 h-4 shrink-0" />
            <span className="text-sm font-semibold truncate">
              {isLowMastery ? "Low mastery review" : "Read"} · Group {groupNumber}
            </span>
          </div>
          <span className="text-xs font-mono tabular-nums shrink-0">
            {index + 1}/{total}
          </span>
        </div>
        <Progress value={pct} className="h-1.5" />
        <p className="text-[11px] text-muted-foreground">
          Read only — progress updates in the quiz. Space / → next · Esc back
        </p>
      </div>

      <div className="flex-1 min-h-0">{current && <WordCard word={current} />}</div>

      <footer className="shrink-0 flex flex-wrap gap-2 justify-between gloss-panel rounded-2xl p-3">
        <Button variant="outline" size="sm" onClick={onBack}>
          Exit
        </Button>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => go(-1)} disabled={index === 0}>
            <ChevronLeft className="w-4 h-4" />
          </Button>
          <Button size="sm" onClick={() => go(1)}>
            {index >= total - 1 ? "Start quiz" : "Next"}
            <ChevronRight className="w-4 h-4 ml-1" />
          </Button>
        </div>
      </footer>
    </div>
  );
}
