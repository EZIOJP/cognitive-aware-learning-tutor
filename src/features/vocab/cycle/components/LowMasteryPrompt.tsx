import { Button } from "../../../../app/components/ui/button";
import { Card } from "../../../../app/components/ui/card";
import { Badge } from "../../../../app/components/ui/badge";
import type { WordWithProgress } from "../../types";

interface LowMasteryPromptProps {
  words: WordWithProgress[];
  cycleCount: number;
  maxCycles?: number;
  onRepeat: () => void;
  onSkip: () => void;
  onBack: () => void;
}

export function LowMasteryPrompt({
  words,
  cycleCount,
  maxCycles = 5,
  onRepeat,
  onSkip,
  onBack,
}: LowMasteryPromptProps) {
  const atMax = cycleCount >= maxCycles;

  return (
    <div className="h-full flex items-center justify-center p-4">
      <Card className="gloss-panel max-w-lg w-full p-8 text-center">
        <div className="text-5xl mb-4">{atMax ? "🔄" : "⚠️"}</div>
        <h2 className="text-xl font-semibold mb-2">
          {atMax ? "Maximum review cycles" : "Low mastery detected"}
        </h2>
        <p className="text-sm text-muted-foreground mb-4">
          {atMax
            ? `You've completed ${maxCycles} review cycles. ${words.length} words remain for a future session.`
            : `${words.length} words are still at mastery ≤ 0. Review them again?`}
        </p>

        {!atMax && (
          <>
            <div className="flex flex-wrap gap-1.5 justify-center mb-4">
              {words.slice(0, 10).map((w) => (
                <Badge key={w.id} variant="destructive" className="font-normal">
                  {w.word}
                </Badge>
              ))}
              {words.length > 10 && (
                <Badge variant="secondary">+{words.length - 10}</Badge>
              )}
            </div>
            <div className="flex justify-center gap-1 mb-6">
              {Array.from({ length: maxCycles }).map((_, i) => (
                <div
                  key={i}
                  className={`w-2.5 h-2.5 rounded-full ${
                    i < cycleCount ? "bg-amber-500" : "bg-muted"
                  }`}
                />
              ))}
            </div>
            <div className="flex flex-wrap gap-2 justify-center">
              <Button onClick={onRepeat}>Review again</Button>
              <Button variant="outline" onClick={onSkip}>
                Skip for now
              </Button>
            </div>
          </>
        )}

        {atMax && (
          <Button className="mb-4" onClick={onSkip}>
            Continue
          </Button>
        )}

        <Button variant="ghost" size="sm" className="mt-4" onClick={onBack}>
          Back to dashboard
        </Button>
      </Card>
    </div>
  );
}
