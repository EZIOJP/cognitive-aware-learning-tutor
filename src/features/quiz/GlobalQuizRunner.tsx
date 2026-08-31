import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router";
import { Clock, Lightbulb, Loader2, Play } from "lucide-react";
import { Button } from "../../app/components/ui/button";
import { Progress } from "../../app/components/ui/progress";
import { PythonCodeBlock } from "../../components/study/PythonCodeBlock";
import { rebuildHubDaily } from "../../api/hubClient";
import { submitTrainSample } from "../../api/mathClient";
import {
  completeGlobalQuiz,
  fetchGlobalQuizQuestion,
  startGlobalQuiz,
  submitGlobalQuizAnswer,
} from "../../api/globalQuizClient";
import type { GlobalQuizQuestion, QuizDomain, QuizSessionSummary } from "./types";
import {
  MathQuizAnswerPanel,
  type MathQuizOcrMeta,
} from "./MathQuizAnswerPanel";
import { useEaster } from "../../easter";

type Props = {
  domain?: QuizDomain;
  config?: Record<string, unknown>;
  /** Resume an existing session instead of POST /start */
  sessionId?: string;
  /** When false, stay on complete screen (for Lecture Notes embeds). Default true. */
  navigateOnComplete?: boolean;
  onDone?: (summary: QuizSessionSummary) => void;
  onClose?: () => void;
};

function formatMs(ms: number): string {
  const s = Math.max(0, Math.floor(ms / 1000));
  const m = Math.floor(s / 60);
  return `${m}:${String(s % 60).padStart(2, "0")}`;
}

export function GlobalQuizRunner({
  domain,
  config = {},
  sessionId: resumeSessionId,
  navigateOnComplete = true,
  onDone,
  onClose,
}: Props) {
  const navigate = useNavigate();
  const { burst } = useEaster();
  const [sessionId, setSessionId] = useState<string | null>(resumeSessionId ?? null);
  const [question, setQuestion] = useState<GlobalQuizQuestion | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [freeText, setFreeText] = useState("");
  const [feedback, setFeedback] = useState<string | null>(null);
  const [lastCorrect, setLastCorrect] = useState<boolean | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [startedAt, setStartedAt] = useState(Date.now());
  const [summary, setSummary] = useState<QuizSessionSummary | null>(null);
  const [showHint, setShowHint] = useState(false);
  const [now, setNow] = useState(Date.now());
  const [sessionDeadline, setSessionDeadline] = useState<number | undefined>(undefined);
  const [ocrMeta, setOcrMeta] = useState<MathQuizOcrMeta | null>(null);
  const [ocrSubmitOk, setOcrSubmitOk] = useState(true);
  const [holdAdvance, setHoldAdvance] = useState(false);
  const pendingNextRef = useRef<GlobalQuizQuestion | null | undefined>(undefined);
  const timedOutRef = useRef(false);
  const hintRevealsRef = useRef(0);

  const configKey = useMemo(() => JSON.stringify(config), [config]);
  const isMathHandwrite =
    question?.domain === "math" && question.format === "free_text";

  const perQuestionSec =
    question?.meta?.per_question_sec ??
    (typeof config.per_question_sec === "number" ? config.per_question_sec : undefined);

  useEffect(() => {
    const t = window.setInterval(() => setNow(Date.now()), 250);
    return () => window.clearInterval(t);
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setBusy(true);
      setError(null);
      setSummary(null);
      setSessionDeadline(undefined);
      try {
        if (resumeSessionId) {
          const res = await fetchGlobalQuizQuestion(resumeSessionId);
          if (cancelled) return;
          if (!res.question) {
            setError("This quiz session has no remaining questions.");
            return;
          }
          setSessionId(resumeSessionId);
          setQuestion(res.question);
          setStartedAt(Date.now());
          const metaDeadline = res.question?.meta?.session_deadline_ms;
          if (typeof metaDeadline === "number") setSessionDeadline(metaDeadline);
        } else {
          if (!domain) {
            setError("Missing quiz domain");
            return;
          }
          const res = await startGlobalQuiz(domain, config);
          if (cancelled) return;
          setSessionId(res.session_id);
          setQuestion(res.question);
          setStartedAt(Date.now());
          const metaDeadline = res.question?.meta?.session_deadline_ms;
          if (typeof metaDeadline === "number") {
            setSessionDeadline(metaDeadline);
          } else if (typeof config.time_limit_sec === "number" && Number(config.time_limit_sec) > 0) {
            setSessionDeadline(Date.now() + Number(config.time_limit_sec) * 1000);
          }
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Could not start quiz");
      } finally {
        if (!cancelled) setBusy(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [domain, configKey, resumeSessionId]);

  useEffect(() => {
    if (question?.format === "code") {
      setFreeText(question.starter_code ?? "");
    } else {
      setFreeText("");
    }
    setSelected(null);
    setFeedback(null);
    setLastCorrect(null);
    setShowHint(false);
    setOcrMeta(null);
    setOcrSubmitOk(true);
    setHoldAdvance(false);
    pendingNextRef.current = undefined;
    setStartedAt(Date.now());
    timedOutRef.current = false;
  }, [question?.item_id, question?.format, question?.starter_code]);

  const questionTimeLeft = perQuestionSec
    ? perQuestionSec * 1000 - (now - startedAt)
    : null;
  const sessionTimeLeft = sessionDeadline ? sessionDeadline - now : null;

  const advance = useCallback(
    async (next: GlobalQuizQuestion | null | undefined) => {
      if (next) {
        setQuestion(next);
        return;
      }
      if (sessionId) {
        const result = await completeGlobalQuiz(sessionId);
        setSummary(result);
        onDone?.(result);
        void rebuildHubDaily();
        if (navigateOnComplete) {
          navigate("/review?tab=due");
        }
      }
      setQuestion(null);
    },
    [sessionId, onDone, navigate, navigateOnComplete]
  );

  const logOcrCorrectionIfNeeded = useCallback(
    async (confirmed: string) => {
      if (!ocrMeta || !confirmed.trim()) return;
      const predicted = (ocrMeta.predictedLatex || "").trim();
      const confirmedNorm = confirmed.trim();
      if (!predicted) return;
      const action =
        predicted.replace(/\s+/g, "") === confirmedNorm.replace(/\s+/g, "")
          ? "confirm"
          : "correct";
      await submitTrainSample({
        tier: "quiz",
        prompt_id: question?.item_id || "math-quiz",
        prompt_text: question?.prompt?.slice(0, 200) || "math quiz",
        canvas_image: ocrMeta.canvasImage,
        predicted_latex: predicted,
        confirmed_latex: confirmedNorm,
        action,
        paths_json: ocrMeta.pathsJson,
        stroke_metrics_json: ocrMeta.strokeMetricsJson,
        target_latex: confirmedNorm,
      });
    },
    [ocrMeta, question?.item_id, question?.prompt]
  );

  const submit = async (timedOut = false) => {
    if (!sessionId || !question || busy) return;
    if (timedOut && timedOutRef.current) return;
    if (timedOut) timedOutRef.current = true;
    const response =
      question.format === "mcq"
        ? timedOut
          ? ""
          : (selected ?? "")
        : timedOut
          ? freeText || "(timed out)"
          : freeText;
    if (!timedOut && !response.trim()) return;
    if (!timedOut && isMathHandwrite && ocrMeta && !ocrSubmitOk) {
      setError("Confirm or edit the OCR reading before submitting.");
      return;
    }
    setBusy(true);
    try {
      if (isMathHandwrite && ocrMeta && !timedOut) {
        void logOcrCorrectionIfNeeded(response);
      }
      const result = await submitGlobalQuizAnswer(sessionId, {
        item_id: question.item_id,
        response,
        time_taken_ms: Date.now() - startedAt,
      });
      const correct = timedOut ? false : result.correct;
      let fb = timedOut ? "Time's up — marked incorrect." : result.feedback;
      if (!correct && result.requeued) {
        fb = `${fb}\n\nRe-added to this session — you'll see it again.`;
      }
      setFeedback(fb);
      setLastCorrect(correct);
      // Math OCR: pause so you can review recognition before next Q
      if (isMathHandwrite && !timedOut) {
        setHoldAdvance(true);
        pendingNextRef.current = result.complete ? null : result.next_question;
        return;
      }
      const pauseMs = timedOut ? 400 : correct ? 900 : 2200;
      if (result.complete) {
        setTimeout(async () => {
          await advance(null);
        }, pauseMs);
      } else if (result.next_question) {
        setTimeout(async () => {
          await advance(result.next_question);
        }, pauseMs);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Submit failed");
    } finally {
      setBusy(false);
    }
  };

  const continueAfterMath = async () => {
    const next = pendingNextRef.current;
    setHoldAdvance(false);
    pendingNextRef.current = undefined;
    await advance(next);
  };

  useEffect(() => {
    if (!question || feedback || busy || timedOutRef.current || holdAdvance) return;
    if (questionTimeLeft !== null && questionTimeLeft <= 0) {
      void submit(true);
      return;
    }
    if (sessionTimeLeft !== null && sessionTimeLeft <= 0) {
      void submit(true);
    }
  }, [question, questionTimeLeft, sessionTimeLeft, feedback, busy, holdAdvance]); // eslint-disable-line

  if (error) {
    return (
      <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-4 text-sm">
        <p>{error}</p>
        {onClose && (
          <Button variant="outline" size="sm" className="mt-3" onClick={onClose}>
            Close
          </Button>
        )}
      </div>
    );
  }

  if (busy && !question && !summary) {
    return (
      <div className="flex items-center gap-2 p-6 text-muted-foreground">
        <Loader2 className="h-5 w-5 animate-spin" />
        Starting quiz…
      </div>
    );
  }

  if (!question && summary) {
    return (
      <div className="flex flex-col gap-4 p-6">
        <h2 className="text-lg font-semibold">Quiz complete</h2>
        <p className="text-3xl font-bold text-primary">
          {summary.correct}/{summary.total}
          <span className="text-base font-normal text-muted-foreground ml-2">
            ({summary.accuracy_pct ?? 0}%)
          </span>
        </p>
        {summary.total_time_ms != null && (
          <p className="text-sm text-muted-foreground flex items-center gap-1">
            <Clock className="h-4 w-4" /> Total time {formatMs(summary.total_time_ms)}
          </p>
        )}
        <p className="text-sm text-emerald-600">Cards added to your spaced repetition queue.</p>
        {summary.next_step && (
          <Button asChild className="self-start gap-1">
            <Link to={summary.next_step.to}>
              <Play className="h-4 w-4" /> Next: {summary.next_step.label}
            </Link>
          </Button>
        )}
        {summary.attempts && summary.attempts.length > 0 && (
          <ul className="text-xs divide-y rounded-lg border max-h-40 overflow-y-auto">
            {summary.attempts.map((a, i) => (
              <li key={i} className="flex justify-between px-3 py-1.5">
                <span className="truncate">{a.label ?? a.item_id}</span>
                <span className={a.correct ? "text-emerald-600" : "text-amber-600"}>
                  {a.correct ? "✓" : "✗"}
                </span>
              </li>
            ))}
          </ul>
        )}
        {onClose && (
          <div className="flex flex-wrap gap-2 self-start">
            <Button variant="outline" asChild>
              <Link to="/review?tab=due">
                <Play className="h-4 w-4 mr-1" /> Review Hub
              </Link>
            </Button>
            <Button onClick={onClose}>Done</Button>
          </div>
        )}
      </div>
    );
  }

  if (!question) {
    return <div className="p-4 text-sm text-muted-foreground">Quiz ended.</div>;
  }

  const pct = question.total > 0 ? Math.round((question.index / question.total) * 100) : 0;
  const hint = question.meta?.hint as string | undefined;

  return (
    <div className="flex flex-col gap-4 p-4">
      <div className="flex items-center justify-between text-xs text-muted-foreground gap-2">
        <span className="uppercase tracking-wide">{question.domain}</span>
        <div className="flex items-center gap-3">
          {sessionTimeLeft != null && (
            <span className={sessionTimeLeft < 30_000 ? "text-amber-600 font-medium" : ""}>
              <Clock className="inline h-3 w-3 mr-0.5" />
              {formatMs(sessionTimeLeft)}
            </span>
          )}
          {questionTimeLeft != null && (
            <span className={questionTimeLeft < 10_000 ? "text-amber-600 font-medium" : ""}>
              Q {formatMs(questionTimeLeft)}
            </span>
          )}
          <span>
            {question.index} / {question.total}
          </span>
        </div>
      </div>
      <Progress value={pct} className="h-1.5" />
      {question.meta?.topic && (
        <p className="text-[10px] uppercase tracking-wide text-muted-foreground">{question.meta.topic}</p>
      )}
      <div
        className="prose prose-sm dark:prose-invert max-w-none"
        dangerouslySetInnerHTML={{ __html: question.prompt.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>") }}
      />

      {question.format === "mcq" && question.options && (
        <div className="flex flex-col gap-2">
          {question.options.map((opt) => (
            <button
              key={opt}
              type="button"
              disabled={!!feedback}
              onClick={() => setSelected(opt)}
              className={`rounded-lg border px-3 py-2 text-left text-sm transition ${
                selected === opt ? "border-primary bg-primary/10" : "border-border hover:bg-muted/50"
              }`}
            >
              {opt}
            </button>
          ))}
        </div>
      )}

      {question.format === "free_text" && isMathHandwrite && (
        <MathQuizAnswerPanel
          disabled={!!feedback}
          value={freeText}
          onChange={setFreeText}
          onOcrMetaChange={setOcrMeta}
          onOcrConfirmChange={setOcrSubmitOk}
          resetKey={question.item_id}
        />
      )}

      {question.format === "free_text" && !isMathHandwrite && (
        <textarea
          className="min-h-[120px] w-full rounded-lg border bg-background p-3 font-mono text-sm"
          value={freeText}
          onChange={(e) => setFreeText(e.target.value)}
          placeholder="Your answer"
          disabled={!!feedback}
        />
      )}

      {question.format === "code" && (
        <PythonCodeBlock
          code={freeText || (question.starter_code ?? "")}
          onCodeChange={setFreeText}
          readOnly={!!feedback}
        />
      )}

      {hint && !feedback && (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="self-start text-xs gap-1"
          onClick={() => {
            setShowHint((v) => {
              if (!v) {
                hintRevealsRef.current += 1;
                if (hintRevealsRef.current >= 7) {
                  hintRevealsRef.current = 0;
                  burst("glow");
                }
              }
              return !v;
            });
          }}
        >
          <Lightbulb className="h-3.5 w-3.5" />
          {showHint ? "Hide hint" : "Show hint"}
        </Button>
      )}
      {showHint && hint && <p className="text-sm text-muted-foreground border-l-2 pl-3">{hint}</p>}

      {feedback && (
        <div className="space-y-1">
          <p
            className={`text-sm whitespace-pre-wrap ${lastCorrect ? "text-emerald-600" : "text-amber-600"}`}
          >
            {feedback}
          </p>
          {!lastCorrect && question.meta?.concept ? (
            <p className="text-xs text-muted-foreground">
              Hint topic: {String(question.meta.concept)}
            </p>
          ) : null}
          {ocrMeta && (
            <p className="text-xs text-muted-foreground">
              OCR saw: <code className="font-mono">{ocrMeta.predictedLatex || "—"}</code>
              {freeText.trim() && freeText.trim() !== ocrMeta.predictedLatex.trim()
                ? ` · you submitted: ${freeText.trim()}`
                : ""}{" "}
              (edits are logged for OCR training)
            </p>
          )}
          {question.meta?.citation ? (
            <p className="text-xs text-muted-foreground">Source: {String(question.meta.citation)}</p>
          ) : null}
        </div>
      )}

      <div className="flex gap-2">
        {!feedback && (
          <Button onClick={() => void submit()} disabled={busy || (isMathHandwrite && !!ocrMeta && !ocrSubmitOk)}>
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : "Submit"}
          </Button>
        )}
        {holdAdvance && (
          <Button onClick={() => void continueAfterMath()} disabled={busy}>
            Continue
          </Button>
        )}
        {onClose && (
          <Button variant="ghost" onClick={onClose}>
            Exit
          </Button>
        )}
      </div>
    </div>
  );
}
