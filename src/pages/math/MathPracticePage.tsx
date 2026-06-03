import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router";
import { ArrowLeft, CheckCircle2, RefreshCw, XCircle } from "lucide-react";
import {
  MathSplitWhiteboard,
  type MathSplitWhiteboardHandle,
} from "../../app/components/MathSplitWhiteboard";
import { PostSessionDiagnostics } from "../../app/components/PostSessionDiagnostics";
import { Button } from "../../app/components/ui/button";
import { Card } from "../../app/components/ui/card";
import { Input } from "../../app/components/ui/input";
import { Badge } from "../../app/components/ui/badge";
import { useAuth } from "../../context/AuthContext";
import { useStudySession } from "../../context/StudySessionContext";
import { authFetch } from "../../features/vocab/api/authClient";
import { getMathTopic, LOCAL_QUESTION_SETS } from "../../features/math/data/topics";

interface MathProblem {
  generated_id: string;
  template_id: number | null;
  question_id?: number | null;
  title: string;
  topic: string;
  prompt: string;
  expected_answer: string;
  explanation: string;
  source?: string;
}

function formatTimer(sec: number) {
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function normalizeAnswer(v: string) {
  return v.toLowerCase().trim().replace(/\s+/g, "").replace(/\^/g, "^");
}

export function MathPracticePage() {
  const { topicId = "algebra" } = useParams();
  const topic = getMathTopic(topicId);
  const { token } = useAuth();
  const {
    handleCanvasChange,
    showDiagnostics,
    setShowDiagnostics,
    diagnosticsSummary,
    handleNewSession,
    biometricData,
    cognitiveLoad,
  } = useStudySession();
  const [tutorHint, setTutorHint] = useState<string | null>(null);
  const [tutorUsesLlm, setTutorUsesLlm] = useState(false);
  const [tutorLoading, setTutorLoading] = useState(false);
  const whiteboardRef = useRef<MathSplitWhiteboardHandle>(null);

  const localSet = LOCAL_QUESTION_SETS[topicId];
  const useLocal = Boolean(localSet?.length);
  const totalQuestions = useLocal ? localSet!.length : 1;

  const [qIndex, setQIndex] = useState(0);
  const [answer, setAnswer] = useState("");
  const [showResult, setShowResult] = useState(false);
  const [correctCount, setCorrectCount] = useState(0);
  const [timer, setTimer] = useState(0);
  const [complete, setComplete] = useState(false);
  const [attempts, setAttempts] = useState<
    { prompt: string; ok: boolean; yours: string; expected: string; timeSpent: number }[]
  >([]);
  const [questionStart, setQuestionStart] = useState(() => Date.now());

  const [apiProblem, setApiProblem] = useState<MathProblem | null>(null);
  const [feedback, setFeedback] = useState<{ ok: boolean; message: string } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const currentLocal = localSet?.[qIndex];
  const progressPct = useLocal
    ? ((qIndex + (showResult ? 1 : 0)) / totalQuestions) * 100
    : showResult
      ? 100
      : 50;

  useEffect(() => {
    if (complete) return;
    const id = setInterval(() => setTimer((t) => t + 1), 1000);
    return () => clearInterval(id);
  }, [complete]);

  useEffect(() => {
    if (!showResult && !complete) setQuestionStart(Date.now());
  }, [qIndex, showResult, complete]);

  const askTutor = async () => {
    if (!token) return;
    setTutorLoading(true);
    try {
      const canvas = await whiteboardRef.current?.exportPng();
      const latest = biometricData[biometricData.length - 1];
      const res = await authFetch("/math/tutor/hint", token, {
        method: "POST",
        body: JSON.stringify({
          canvas_image: canvas ?? "",
          prompt: apiProblem?.prompt ?? currentLocal?.question ?? "",
          topic: topic?.label ?? topicId,
          gamma: latest?.gamma ?? 0,
          attention: 0,
        }),
      });
      const data = await res.json();
      setTutorUsesLlm(Boolean(data.use_llm));
      setTutorHint(`${data.hint}\n\n${data.question}`);
    } catch {
      setTutorHint("Could not reach tutor — check backend is running.");
    } finally {
      setTutorLoading(false);
    }
  };

  const loadApiProblem = useCallback(async () => {
    if (!token || useLocal) return;
    setLoading(true);
    setError("");
    try {
      const topicParam = topic?.backendTopic ? `?topic=${encodeURIComponent(topic.backendTopic)}` : "";
      const res = await authFetch(`/math/practice/next${topicParam}`, token);
      setApiProblem((res.data as { problem: MathProblem }).problem);
      setAnswer("");
      setShowResult(false);
      setFeedback(null);
      await whiteboardRef.current?.clearAll();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load problem");
    } finally {
      setLoading(false);
    }
  }, [token, topic?.backendTopic, useLocal]);

  useEffect(() => {
    if (!useLocal) loadApiProblem();
  }, [useLocal, loadApiProblem]);

  const submitLocal = () => {
    if (!currentLocal || !answer.trim()) return;
    const ok =
      normalizeAnswer(answer) === normalizeAnswer(currentLocal.answer) ||
      answer.toLowerCase().trim() === currentLocal.answer.toLowerCase().trim();
    if (ok) setCorrectCount((c) => c + 1);
    const timeSpent = Math.floor((Date.now() - questionStart) / 1000);
    setAttempts((a) => [
      ...a,
      {
        prompt: currentLocal.question,
        ok,
        yours: answer,
        expected: currentLocal.answer,
        timeSpent,
      },
    ]);
    setShowResult(true);
  };

  const nextLocal = async () => {
    if (!localSet) return;
    await whiteboardRef.current?.clearAll();
    if (qIndex < localSet.length - 1) {
      setQIndex((i) => i + 1);
      setAnswer("");
      setShowResult(false);
    } else {
      setComplete(true);
    }
  };

  const submitApi = async () => {
    if (!token || !apiProblem || !answer.trim()) return;
    try {
      const res = await authFetch("/math/practice/submit", token, {
        method: "POST",
        body: JSON.stringify({
          generated_id: apiProblem.generated_id,
          template_id: apiProblem.template_id ?? null,
          question_id: apiProblem.question_id ?? null,
          topic: apiProblem.topic,
          prompt: apiProblem.prompt,
          expected_answer: apiProblem.expected_answer,
          user_answer: answer,
        }),
      });
      const data = res.data as { is_correct: boolean; mastery_delta: number; expected_answer: string };
      setFeedback({
        ok: data.is_correct,
        message: data.is_correct
          ? `Correct (+${data.mastery_delta} mastery)`
          : `Expected ${data.expected_answer}`,
      });
      setShowResult(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Submit failed");
    }
  };

  const nextApi = async () => {
    await whiteboardRef.current?.clearAll();
    loadApiProblem();
  };

  const sessionSummary = useMemo(
    () => ({
      duration: timer,
      totalProblems: attempts.length || (complete ? localSet?.length ?? 0 : 0),
      interventions: attempts.filter((a) => !a.ok).length,
      stressPoints: [],
      overallPerformance:
        correctCount / (localSet?.length || 1) >= 0.8
          ? ("excellent" as const)
          : correctCount / (localSet?.length || 1) >= 0.5
            ? ("good" as const)
            : ("needs-improvement" as const),
    }),
    [timer, attempts, complete, localSet, correctCount]
  );

  if (complete) {
    return (
      <div className="h-full flex flex-col gap-3 min-h-0">
        <Card className="gloss-panel p-6 max-w-xl mx-auto space-y-4 my-auto">
          <h2 className="text-xl font-semibold">Quiz complete</h2>
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div className="rounded-lg border p-3">
              <p className="text-muted-foreground text-xs">Score</p>
              <p className="text-lg font-semibold">
                {correctCount}/{localSet?.length}
              </p>
            </div>
            <div className="rounded-lg border p-3">
              <p className="text-muted-foreground text-xs">Time</p>
              <p className="text-lg font-semibold font-mono">{formatTimer(timer)}</p>
            </div>
          </div>
          <div className="space-y-2 max-h-48 overflow-y-auto">
            {attempts.map((a, i) => (
              <div
                key={i}
                className={`text-xs border rounded p-2 ${a.ok ? "border-emerald-500/40" : "border-red-500/40"}`}
              >
                Q{i + 1}: {a.ok ? "✓" : "✗"} {a.prompt.slice(0, 60)}… ({a.timeSpent}s)
              </div>
            ))}
          </div>
          <div className="flex gap-2">
            <Button onClick={() => setShowDiagnostics(true)}>View report</Button>
            <Button variant="outline" asChild>
              <Link to="/math-tutor">Dashboard</Link>
            </Button>
          </div>
        </Card>
        {showDiagnostics && (
          <PostSessionDiagnostics
            summary={sessionSummary}
            onClose={() => setShowDiagnostics(false)}
            onNewSession={handleNewSession}
          />
        )}
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col min-h-0">
      <div className="flex-1 flex flex-col xl:flex-row min-h-0 gap-0 gloss-panel rounded-2xl overflow-hidden">
        {/* Left: question panel */}
        <div className="w-full xl:w-[min(100%,360px)] shrink-0 flex flex-col border-b xl:border-b-0 xl:border-r p-4 gap-4 overflow-y-auto">
          <div className="flex items-center justify-between gap-2">
            <Link
              to={topic ? `/math-tutor/topic/${topic.id}` : "/math-tutor"}
              className="inline-flex items-center gap-1 text-sm text-primary hover:underline"
            >
              <ArrowLeft className="w-4 h-4" />
              {topic?.label ?? "Math"}
            </Link>
            <Badge variant="outline" className="font-mono">
              {formatTimer(timer)}
            </Badge>
          </div>

          {useLocal && localSet && (
            <div>
              <div className="flex justify-between text-xs text-muted-foreground mb-1">
                <span>Progress</span>
                <span>
                  {qIndex + 1} / {localSet.length}
                </span>
              </div>
              <div className="h-2 rounded-full bg-muted overflow-hidden">
                <div
                  className="h-full bg-primary transition-all duration-300"
                  style={{ width: `${Math.min(100, progressPct)}%` }}
                />
              </div>
            </div>
          )}

          {useLocal && currentLocal ? (
            <>
              <p className="text-lg font-medium leading-snug">{currentLocal.question}</p>
              <Input
                value={answer}
                disabled={showResult}
                onChange={(e) => setAnswer(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && !showResult && submitLocal()}
                placeholder="Your answer"
              />
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="w-full"
                disabled={tutorLoading}
                onClick={() => void askTutor()}
              >
                {tutorLoading ? "Asking tutor…" : `Ask tutor (${cognitiveLoad} load)`}
              </Button>
              {tutorHint && (
                <div className="space-y-1">
                  <p className="text-[10px] text-muted-foreground">
                    {tutorUsesLlm ? "Ollama tutor" : "Built-in coach (no GPU / AI required)"}
                  </p>
                  <p className="text-xs text-muted-foreground whitespace-pre-wrap border rounded-lg p-2 bg-muted/30">
                    {tutorHint}
                  </p>
                </div>
              )}
              {!showResult ? (
                <Button onClick={submitLocal} disabled={!answer.trim()} className="w-full">
                  Submit
                </Button>
              ) : (
                <>
                  <div className="text-sm rounded-lg border p-3 space-y-1">
                    <p className="font-medium flex items-center gap-2">
                      {attempts[attempts.length - 1]?.ok ? (
                        <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                      ) : (
                        <XCircle className="w-4 h-4 text-red-500" />
                      )}
                      Answer: {currentLocal.answer}
                    </p>
                    <p className="text-muted-foreground">{currentLocal.explanation}</p>
                  </div>
                  <Button onClick={nextLocal} className="w-full">
                    {qIndex < (localSet?.length ?? 1) - 1 ? "Next question →" : "Finish quiz"}
                  </Button>
                </>
              )}
            </>
          ) : (
            <>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="w-full"
                disabled={!token || tutorLoading}
                onClick={() => void askTutor()}
              >
                {tutorLoading ? "Asking tutor…" : `Ask tutor (${cognitiveLoad} load)`}
              </Button>
              {tutorHint && (
                <div className="space-y-1">
                  <p className="text-[10px] text-muted-foreground">
                    {tutorUsesLlm ? "Ollama tutor" : "Built-in coach (no GPU / AI required)"}
                  </p>
                  <p className="text-xs text-muted-foreground whitespace-pre-wrap border rounded-lg p-2 bg-muted/30">
                    {tutorHint}
                  </p>
                </div>
              )}
              {error && <p className="text-sm text-destructive">{error}</p>}
              {!token && (
                <p className="text-sm text-muted-foreground">Log in for API-backed {topic?.label} drills.</p>
              )}
              {apiProblem && (
                <>
                  <p className="text-lg font-semibold leading-snug">{apiProblem.prompt}</p>
                  <Input
                    value={answer}
                    disabled={showResult}
                    onChange={(e) => setAnswer(e.target.value)}
                    placeholder="Answer"
                  />
                  {!showResult ? (
                    <div className="flex gap-2">
                      <Button onClick={submitApi} disabled={!answer.trim()} className="flex-1">
                        Submit
                      </Button>
                      <Button size="icon" variant="outline" onClick={loadApiProblem} disabled={loading}>
                        <RefreshCw className="w-4 h-4" />
                      </Button>
                    </div>
                  ) : (
                    <>
                      {feedback && (
                        <div className="flex items-center gap-2 text-sm rounded-lg border p-3">
                          {feedback.ok ? (
                            <CheckCircle2 className="w-4 h-4 text-green-500" />
                          ) : (
                            <XCircle className="w-4 h-4 text-red-500" />
                          )}
                          {feedback.message}
                        </div>
                      )}
                      <Button onClick={nextApi} className="w-full">
                        Next problem →
                      </Button>
                    </>
                  )}
                </>
              )}
            </>
          )}
        </div>

        {/* Right: split whiteboard */}
        <div className="flex-1 min-h-[280px] min-w-0">
          <MathSplitWhiteboard ref={whiteboardRef} onCanvasChange={handleCanvasChange} />
        </div>
      </div>

      {showDiagnostics && (
        <PostSessionDiagnostics
          summary={sessionSummary}
          onClose={() => setShowDiagnostics(false)}
          onNewSession={handleNewSession}
        />
      )}
    </div>
  );
}
