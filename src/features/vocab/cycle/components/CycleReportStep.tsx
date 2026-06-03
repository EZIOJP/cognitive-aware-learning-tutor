import { Loader2 } from "lucide-react";
import { Button } from "../../../../app/components/ui/button";
import { Card } from "../../../../app/components/ui/card";
import { Badge } from "../../../../app/components/ui/badge";
import type { QuizResults } from "../types";
import type { WordWithProgress } from "../../types";

interface CycleReportStepProps {
  results: QuizResults;
  isLowMasteryMode?: boolean;
  lowMasteryWords: WordWithProgress[];
  onStartLowMastery: () => void;
  onContinue: () => void;
  onBack: () => void;
  loadingLowMastery?: boolean;
}

export function CycleReportStep({
  results,
  isLowMasteryMode = false,
  lowMasteryWords,
  onStartLowMastery,
  onContinue,
  onBack,
  loadingLowMastery = false,
}: CycleReportStepProps) {
  const { performance, attempts } = results;
  const accuracy = performance.accuracy_rate;
  const lowCount = lowMasteryWords.length;

  const level =
    accuracy >= 90
      ? { label: "Excellent", emoji: "🌟" }
      : accuracy >= 75
        ? { label: "Good", emoji: "✅" }
        : accuracy >= 60
          ? { label: "Fair", emoji: "⚡" }
          : { label: "Needs practice", emoji: "🎯" };

  return (
    <div className="h-full overflow-y-auto space-y-4">
      <div className="gloss-panel rounded-2xl p-6 text-center">
        <div className="text-4xl mb-2">{level.emoji}</div>
        <h2 className="text-xl font-semibold mb-1">
          {isLowMasteryMode ? "Low mastery round complete" : "Cycle complete"}
        </h2>
        <p className="text-muted-foreground text-sm">{level.label}</p>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: "Questions", value: performance.total_questions },
          { label: "Correct", value: performance.correct_answers },
          { label: "Accuracy", value: `${accuracy}%` },
          { label: "Improved", value: performance.words_improved },
        ].map(({ label, value }) => (
          <Card key={label} className="gloss-panel p-4 text-center">
            <div className="text-2xl font-bold font-mono tabular-nums">{value}</div>
            <div className="text-xs text-muted-foreground mt-1">{label}</div>
          </Card>
        ))}
      </div>

      {attempts.length > 0 && (
        <Card className="gloss-panel p-4">
          <h3 className="text-sm font-semibold mb-3">Mastery changes</h3>
          <ul className="space-y-2 max-h-48 overflow-y-auto">
            {attempts.slice(0, 12).map((a) => (
              <li
                key={`${a.word_id}-${a.time_taken}`}
                className="flex items-center justify-between text-sm gap-2"
              >
                <span className="font-medium truncate">{a.word}</span>
                <span className="font-mono tabular-nums shrink-0 flex items-center gap-1">
                  <span className="text-muted-foreground">{a.mastery_before}</span>
                  <span>→</span>
                  <span className={a.mastery_after <= 0 ? "text-destructive" : ""}>
                    {a.mastery_after}
                  </span>
                  <Badge
                    variant={a.is_correct ? "secondary" : "destructive"}
                    className="text-[10px] ml-1"
                  >
                    {a.is_correct ? "✓" : "✗"}
                  </Badge>
                </span>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {!isLowMasteryMode && lowCount > 0 && (
        <Card className="gloss-panel p-4 border-amber-500/30">
          <h3 className="font-semibold mb-2">
            {lowCount} word{lowCount !== 1 ? "s" : ""} still at low mastery
          </h3>
          <div className="flex flex-wrap gap-1.5 mb-4">
            {lowMasteryWords.slice(0, 8).map((w) => (
              <Badge key={w.id} variant="outline">
                {w.word}
              </Badge>
            ))}
            {lowCount > 8 && (
              <Badge variant="secondary">+{lowCount - 8} more</Badge>
            )}
          </div>
          <Button onClick={onStartLowMastery} disabled={loadingLowMastery}>
            {loadingLowMastery ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Loading…
              </>
            ) : (
              "Review low mastery words"
            )}
          </Button>
        </Card>
      )}

      <div className="flex flex-wrap gap-2 justify-end pb-4">
        <Button variant="outline" onClick={onBack}>
          Dashboard
        </Button>
        <Button onClick={onContinue}>
          {lowCount > 0 && !isLowMasteryMode ? "Skip review" : "Done"}
        </Button>
      </div>
    </div>
  );
}
