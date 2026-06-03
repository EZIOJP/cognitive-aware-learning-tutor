import { useCallback, useEffect, useMemo, useState } from "react";
import { Brain, Loader2 } from "lucide-react";
import { Button } from "../../../../app/components/ui/button";
import { Progress } from "../../../../app/components/ui/progress";
import {
  completeAdaptiveQuiz,
  fetchAdaptiveQuestion,
  hasVocabApi,
  startAdaptiveQuiz,
  submitAdaptiveAnswer,
} from "../../../../api/vocabClient";
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

type LocalQuestion = {
  word_id: number;
  word: string;
  pronunciation?: string;
  options: string[];
  correct_answer: string;
};

export function CycleQuizStep({
  words,
  groupNumber,
  isLowMastery = false,
  onComplete,
  onBack,
}: CycleQuizStepProps) {
  const useServer = hasVocabApi();
  const localQuestions = useMemo(
    () => (useServer ? [] : buildQuizQuestions(words)),
    [useServer, words]
  );

  const [sessionId, setSessionId] = useState<string | null>(null);
  const [serverQ, setServerQ] = useState<LocalQuestion | null>(null);
  const [serverTotal, setServerTotal] = useState(0);
  const [serverNum, setServerNum] = useState(0);
  const [initError, setInitError] = useState(false);

  const [qIndex, setQIndex] = useState(0);
  const [selected, setSelected] = useState<string | null>(null);
  const [showFeedback, setShowFeedback] = useState(false);
  const [lastCorrect, setLastCorrect] = useState(false);
  const [attempts, setAttempts] = useState<QuizAttempt[]>([]);
  const [busy, setBusy] = useState(false);
  const [startTime, setStartTime] = useState(Date.now());
  const [booting, setBooting] = useState(useServer);

  const localQ = localQuestions[qIndex];
  const q: LocalQuestion | null = useServer
    ? serverQ
    : localQ
      ? {
          word_id: localQ.word_id,
          word: localQ.word,
          pronunciation: localQ.pronunciation,
          options: localQ.options,
          correct_answer: localQ.correct_answer,
        }
      : null;

  const totalCount = useServer ? serverTotal : localQuestions.length;
  const qNum = useServer ? serverNum : qIndex + 1;

  const pct =
    totalCount > 0
      ? (useServer
          ? (serverNum / totalCount) * 100
          : ((qIndex + (showFeedback ? 1 : 0)) / totalCount) * 100)
      : 0;

  const wordMap = useMemo(
    () => new Map(words.map((w) => [w.id, w])),
    [words]
  );

  const advanceServer = useCallback(
    async (sid: string) => {
      const next = await fetchAdaptiveQuestion(sid);
      if (!next || next.session_complete) {
        const results = await completeAdaptiveQuiz(sid);
        onComplete(results ?? buildQuizResults(sid, []));
        return;
      }
      setServerQ({
        word_id: next.word_id!,
        word: next.word!,
        pronunciation: next.pronunciation,
        options: next.options ?? [],
        correct_answer: "",
      });
      setServerNum(next.question_number ?? 1);
      setServerTotal((t) => next.total_questions ?? t);
    },
    [onComplete]
  );

  useEffect(() => {
    if (!useServer) return;
    let cancelled = false;

    (async () => {
      setBooting(true);
      setInitError(false);
      const started = await startAdaptiveQuiz({
        quiz_type: isLowMastery ? "low_mastery" : "adaptive_group",
        group_number: isLowMastery ? undefined : groupNumber,
        word_ids: isLowMastery ? words.map((w) => w.id) : [],
      });
      if (cancelled) return;
      if (!started?.session_id) {
        setInitError(true);
        setBooting(false);
        return;
      }
      setSessionId(started.session_id);
      setServerTotal(started.total_questions);
      if (started.total_questions === 0) {
        onComplete(buildQuizResults(started.session_id, []));
        setBooting(false);
        return;
      }
      await advanceServer(started.session_id);
      if (!cancelled) setBooting(false);
    })();

    return () => {
      cancelled = true;
    };
  }, [useServer, groupNumber, isLowMastery, words.length, advanceServer, onComplete]);

  useEffect(() => {
    if (!useServer && localQuestions.length === 0) {
      onComplete(buildQuizResults("empty", []));
    }
  }, [useServer, localQuestions.length, onComplete]);

  const goToNextLocal = useCallback(
    (allAttempts: QuizAttempt[]) => {
      if (qIndex + 1 >= localQuestions.length) {
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
    [qIndex, localQuestions.length, groupNumber, onComplete]
  );

  const processSubmit = useCallback(
    async (opt: string) => {
      if (showFeedback || busy || !q) return;
      setSelected(opt);
      setBusy(true);

      try {
        if (useServer && sessionId) {
          const res = await submitAdaptiveAnswer(sessionId, {
            word_id: q.word_id,
            answer: opt,
            time_taken: Date.now() - startTime,
          });
          if (!res) return;
          setLastCorrect(res.is_correct);
          setShowFeedback(true);
          const attempt: QuizAttempt = {
            word_id: q.word_id,
            word: q.word,
            user_answer: opt,
            correct_answer: res.correct_answer,
            is_correct: res.is_correct,
            mastery_before: res.mastery_before,
            mastery_after: res.mastery_after,
            time_taken: Date.now() - startTime,
          };
          setAttempts((prev) => [...prev, attempt]);
          setTimeout(async () => {
            setSelected(null);
            setShowFeedback(false);
            setStartTime(Date.now());
            await advanceServer(sessionId);
          }, res.is_correct ? 1000 : 2500);
        } else {
          const word = wordMap.get(q.word_id);
          if (!word) return;
          const attempt = await submitQuizAnswer(word, opt, Date.now() - startTime);
          setLastCorrect(attempt.is_correct);
          setShowFeedback(true);
          setAttempts((prev) => {
            const next = [...prev, attempt];
            setTimeout(() => goToNextLocal(next), attempt.is_correct ? 1000 : 2500);
            return next;
          });
        }
      } finally {
        setBusy(false);
      }
    },
    [
      showFeedback,
      busy,
      q,
      useServer,
      sessionId,
      startTime,
      wordMap,
      advanceServer,
      goToNextLocal,
    ]
  );

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

  if (booting || initError || !q) {
    return (
      <div className="h-full flex flex-col items-center justify-center gap-3 gloss-panel rounded-2xl p-8">
        {initError ? (
          <>
            <p className="text-sm text-muted-foreground text-center">
              Could not start server quiz. Sign in and ensure the API is running.
            </p>
            <Button variant="outline" onClick={onBack}>
              Back
            </Button>
          </>
        ) : (
          <>
            <Loader2 className="w-8 h-8 animate-spin text-primary" />
            <p className="text-sm text-muted-foreground">Preparing quiz…</p>
          </>
        )}
      </div>
    );
  }

  const correctAnswer =
    useServer && showFeedback && !lastCorrect
      ? attempts[attempts.length - 1]?.correct_answer
      : q.correct_answer;

  return (
    <div className="h-full flex flex-col gap-3 min-h-0 quiz-step-deep">
      <div className="gloss-panel rounded-2xl p-3 shrink-0 space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-sm font-semibold flex items-center gap-2">
            <Brain className="w-4 h-4 text-primary" />
            {isLowMastery ? "Low mastery quiz" : "Quiz"} · G{groupNumber}
          </span>
          <span className="text-xs font-mono tabular-nums text-muted-foreground">
            {qNum}/{totalCount}
          </span>
        </div>
        <Progress value={pct} className="h-1.5" />
      </div>

      <div className="flex-1 gloss-panel rounded-2xl p-5 sm:p-6 flex flex-col min-h-0 overflow-y-auto gap-4">
        <div>
          <p className="text-xs text-muted-foreground mb-1 uppercase tracking-wide">
            What is the meaning of
          </p>
          <h2 className="text-2xl sm:text-3xl font-bold mb-1">{q.word}</h2>
          {q.pronunciation ? (
            <p className="text-muted-foreground text-sm italic">/{q.pronunciation}/</p>
          ) : null}
        </div>

        <div className="grid gap-2">
          {q.options.map((opt, idx) => {
            const isSelected = selected === opt;
            const isCorrect =
              showFeedback &&
              (opt === correctAnswer || attempts[attempts.length - 1]?.correct_answer === opt);

            let variant: "outline" | "default" | "destructive" = "outline";
            if (showFeedback && isCorrect) variant = "default";
            if (showFeedback && isSelected && !isCorrect) variant = "destructive";

            return (
              <Button
                key={`${opt}-${idx}`}
                variant={variant}
                className={[
                  "h-auto py-3 px-4 text-sm text-left justify-start whitespace-normal",
                  "transition-all duration-200",
                  isSelected && !showFeedback
                    ? "border-primary bg-primary/15"
                    : "hover:border-primary/50 hover:bg-primary/5",
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

        {showFeedback ? (
          <div
            className={[
              "p-4 rounded-xl text-center flex flex-col items-center gap-1.5",
              "animate-in zoom-in duration-300",
              lastCorrect
                ? "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border border-emerald-500/30"
                : "bg-destructive/10 text-destructive border border-destructive/30",
            ].join(" ")}
          >
            <span className="font-bold text-lg">
              {lastCorrect ? "Correct" : "Incorrect"}
            </span>
            {!lastCorrect && correctAnswer ? (
              <span className="text-sm font-medium mt-1">
                Answer:{" "}
                <span className="text-foreground font-semibold">{correctAnswer}</span>
              </span>
            ) : null}
          </div>
        ) : null}
      </div>

      <footer className="shrink-0 gloss-panel rounded-2xl p-3 flex items-center justify-between">
        <Button variant="outline" size="sm" onClick={onBack} disabled={busy}>
          Exit Quiz
        </Button>
        <span className="text-xs text-muted-foreground">
          Keys{" "}
          <kbd className="px-1.5 py-0.5 rounded border text-xs font-mono">1</kbd>–
          <kbd className="px-1.5 py-0.5 rounded border text-xs font-mono">4</kbd>
        </span>
      </footer>
    </div>
  );
}
