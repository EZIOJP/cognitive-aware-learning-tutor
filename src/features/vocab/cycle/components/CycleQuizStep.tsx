import { useCallback, useEffect, useMemo, useState } from "react";
import { Brain, Loader2 } from "lucide-react";
import { Button } from "../../../../app/components/ui/button";
import { Progress } from "../../../../app/components/ui/progress";
import type { WordWithProgress } from "../../types";
import type { QuizAttempt } from "../types";
import {
  buildQuizQuestions,
  buildQuizResults,
  submitQuizAnswer,
} from "../cycleService";

interface CycleQuizStepProps {
  words: WordWithProgress[];
  groupNumber: number;
  isLowMastery?: boolean;
  onComplete: (results: ReturnType<typeof buildQuizResults>) => void;
  onBack: () => void;
}

export function CycleQuizStep({
  words,
  groupNumber,
  isLowMastery = false,
  onComplete,
  onBack,
}: CycleQuizStepProps) {
  const questions = useMemo(() => buildQuizQuestions(words), [words]);
  const [qIndex, setQIndex] = useState(0);
  const [selected, setSelected] = useState<string | null>(null);
  const [showFeedback, setShowFeedback] = useState(false);
  const [lastCorrect, setLastCorrect] = useState(false);
  const [attempts, setAttempts] = useState<QuizAttempt[]>([]);
  const [busy, setBusy] = useState(false);
  const [startTime, setStartTime] = useState(Date.now());

  const q = questions[qIndex];

  const wordMap = useMemo(
    () => new Map(words.map((w) => [w.id, w])),
    [words]
  );

  const pct =
    questions.length > 0
      ? ((qIndex + (showFeedback ? 1 : 0)) / questions.length) * 100
      : 0;

  const goToNextQuestion = useCallback(
    (allAttempts: QuizAttempt[]) => {
      if (qIndex + 1 >= questions.length) {
        onComplete(
          buildQuizResults(`cycle-${groupNumber}-${Date.now()}`, allAttempts)
        );
        return;
      }
      setQIndex((i) => i + 1);
      setSelected(null);
      setShowFeedback(false);
      setStartTime(Date.now());
    },
    [qIndex, questions.length, groupNumber, onComplete]
  );

  const processSubmit = useCallback(
    async (opt: string) => {
      if (showFeedback || busy || !q) return;
      setSelected(opt);

      const word = wordMap.get(q.word_id);
      if (!word) return;

      setBusy(true);
      try {
        const attempt = await submitQuizAnswer(word, opt, Date.now() - startTime);
        setLastCorrect(attempt.is_correct);
        setShowFeedback(true);
        setAttempts((prev) => {
          const next = [...prev, attempt];
          setTimeout(
            () => goToNextQuestion(next),
            attempt.is_correct ? 1000 : 2500
          );
          return next;
        });
      } finally {
        setBusy(false);
      }
    },
    [q, busy, showFeedback, wordMap, startTime, goToNextQuestion]
  );

  // Complete quiz immediately when no questions
  useEffect(() => {
    if (questions.length === 0) {
      onComplete(buildQuizResults("empty", []));
    }
  }, [questions.length, onComplete]);

  // Keyboard shortcuts: press 1–4 to directly submit the corresponding option
  useEffect(() => {
    if (!q) return;
    const handleKey = (e: KeyboardEvent) => {
      if (showFeedback || busy) return;
      const index = Number(e.key) - 1;
      if (index >= 0 && index < q.options.length) {
        processSubmit(q.options[index]);
      }
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [showFeedback, busy, q, processSubmit]);

  if (!q) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="w-8 h-8 animate-spin" />
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col gap-3 min-h-0">
      {/* Header / progress */}
      <div className="gloss-panel rounded-2xl p-3 shrink-0 space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-sm font-semibold flex items-center gap-2">
            <Brain className="w-4 h-4" />
            {isLowMastery ? "Low mastery quiz" : "Quiz"} · G{groupNumber}
          </span>
          <span className="text-xs font-mono tabular-nums">
            {qIndex + 1}/{questions.length}
          </span>
        </div>
        <Progress value={pct} className="h-1.5" />
      </div>

      {/* Question + options */}
      <div className="flex-1 gloss-panel rounded-2xl p-5 sm:p-6 flex flex-col min-h-0 overflow-y-auto gap-4">
        <div>
          <p className="text-xs text-muted-foreground mb-1">What is the meaning of</p>
          <h2 className="text-2xl sm:text-3xl font-bold mb-1">{q.word}</h2>
          {q.pronunciation && (
            <p className="text-muted-foreground text-sm italic">/{q.pronunciation}/</p>
          )}
        </div>

        {/* Options — clicking immediately submits */}
        <div className="grid gap-2">
          {q.options.map((opt, idx) => {
            const isSelected = selected === opt;
            const isCorrect = opt === q.correct_answer;

            let variant: "outline" | "default" | "destructive" = "outline";
            if (showFeedback && isCorrect) variant = "default";
            if (showFeedback && isSelected && !isCorrect) variant = "destructive";

            return (
              <Button
                key={opt}
                variant={variant}
                className={[
                  "h-auto py-3 px-4 text-sm text-left justify-start whitespace-normal",
                  "transition-all duration-200",
                  isSelected && !showFeedback
                    ? "border-emerald-500 bg-emerald-500/20 text-emerald-700 dark:text-emerald-300"
                    : "hover:border-emerald-500 hover:bg-emerald-500/10",
                ].join(" ")}
                disabled={showFeedback || busy}
                onClick={() => processSubmit(opt)}
              >
                <span className="font-mono font-semibold mr-2 opacity-60">
                  {idx + 1}.
                </span>
                {opt}
              </Button>
            );
          })}
        </div>

        {/* Feedback banner */}
        {showFeedback && (
          <div
            className={[
              "p-4 rounded-xl text-center flex flex-col items-center gap-1.5",
              "animate-in zoom-in duration-300",
              lastCorrect
                ? "bg-emerald-100 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800"
                : "bg-red-100 dark:bg-red-950/40 text-red-700 dark:text-red-300 border border-red-200 dark:border-red-800",
            ].join(" ")}
          >
            <span className="font-bold text-lg">
              {lastCorrect ? "🎉 Correct!" : "❌ Incorrect"}
            </span>
            {!lastCorrect && (
              <span className="text-sm font-medium mt-1">
                Correct answer:{" "}
                <span className="text-foreground font-semibold">{q.correct_answer}</span>
              </span>
            )}
          </div>
        )}
      </div>

      {/* Footer */}
      <footer className="shrink-0 gloss-panel rounded-2xl p-3 flex items-center justify-between">
        <Button variant="outline" size="sm" onClick={onBack} disabled={busy}>
          Exit Quiz
        </Button>
        <span className="text-xs text-muted-foreground">
          Press <kbd className="px-1.5 py-0.5 rounded border text-xs font-mono">1</kbd>–
          <kbd className="px-1.5 py-0.5 rounded border text-xs font-mono">4</kbd> to answer
        </span>
      </footer>
    </div>
  );
}
