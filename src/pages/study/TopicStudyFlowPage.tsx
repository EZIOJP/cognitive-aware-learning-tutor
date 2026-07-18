import { useEffect, useState } from "react";
import { useNavigate } from "react-router";
import {
  BookOpen,
  BrainCircuit,
  CheckCircle2,
  ChevronRight,
  ClipboardCheck,
  Loader2,
  PlayCircle,
  Rocket,
  Search,
  Zap,
} from "lucide-react";
import {
  startTopicStudyFlow,
  listTranscripts,
  loadLlmPrefs,
  type StudyFlowResult,
  type TranscriptFile,
} from "../../api/transcriptsClient";
import { useEaster, useStepDance } from "../../easter";
import "./TopicStudyFlowPage.css";

/* ──────────────────────────────────────────────── types */
type FlowStep = 0 | 1 | 2 | 3; // config → retrieve+notes → quiz → review

/* ──────────────────────────────────────────────── helpers */
function StepBadge({
  step,
  current,
  label,
  icon: Icon,
  onSelect,
}: {
  step: FlowStep;
  current: FlowStep;
  label: string;
  icon: React.ElementType;
  onSelect?: (step: number) => void;
}) {
  const done = current > step;
  const active = current === step;
  return (
    <div
      role="button"
      tabIndex={0}
      className={`tsf-step ${active ? "active" : ""} ${done ? "done" : ""}`}
      onClick={() => onSelect?.(step + 1)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") onSelect?.(step + 1);
      }}
    >
      <div className="tsf-step-icon">
        {done ? <CheckCircle2 size={16} /> : <Icon size={16} />}
      </div>
      <span className="tsf-step-label">{label}</span>
      {step < 3 && <ChevronRight size={14} className="tsf-step-arrow" />}
    </div>
  );
}

/* ──────────────────────────────────────────────── page */
export function TopicStudyFlowPage() {
  const navigate = useNavigate();
  const { burst } = useEaster();
  const onStepTap = useStepDance([1, 2, 3, 2, 1], () => burst("bounce"));

  /* form state */
  const [topic, setTopic] = useState("");
  const [transcriptFile, setTranscriptFile] = useState("");
  const [folderPath, setFolderPath] = useState("study_flow");
  const [quizCount, setQuizCount] = useState(8);

  /* flow state */
  const [step, setStep] = useState<FlowStep>(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<StudyFlowResult | null>(null);
  const [transcripts, setTranscripts] = useState<TranscriptFile[]>([]);

  /* load transcript list */
  useEffect(() => {
    listTranscripts()
      .then((t) => {
        setTranscripts(t);
        if (t.length > 0) setTranscriptFile(t[0].filename);
      })
      .catch(() => {});
  }, []);

  const handleStart = async () => {
    if (!topic.trim() || !transcriptFile) {
      setError("Topic and transcript file are required.");
      return;
    }
    setLoading(true);
    setError(null);
    setStep(1);

    const llmPrefs = loadLlmPrefs();
    try {
      const data = await startTopicStudyFlow({
        topic: topic.trim(),
        transcriptFile,
        folderPath: folderPath.trim(),
        title: topic.trim(),
        ingestCorpus: false,
        quizCount,
        llm: llmPrefs,
      });
      setResult(data);
      setStep(2);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Study flow failed");
      setStep(0);
    } finally {
      setLoading(false);
    }
  };

  const notesPath = result?.steps.notes.filename ?? "";
  const sessionId = result?.steps.quiz.session_id;
  const questionCount = result?.steps.quiz.question_count ?? 0;
  const hitCount = result?.steps.retrieve.hit_count ?? 0;
  const corpusHandoff = result?.steps.corpus_handoff;

  return (
    <div className="tsf-root">
      {/* ── header ── */}
      <div className="tsf-header">
        <div className="tsf-header-icon">
          <Rocket size={22} />
        </div>
        <div>
          <h1 className="tsf-title">Topic Study Flow</h1>
          <p className="tsf-subtitle">
            One click: transcript notes → quiz deck → SRS review
          </p>
        </div>
      </div>

      {/* ── stepper ── */}
      <div className="tsf-stepper">
        <StepBadge step={0} current={step} label="Configure" icon={Search} onSelect={onStepTap} />
        <StepBadge step={1} current={step} label="Notes" icon={BookOpen} onSelect={onStepTap} />
        <StepBadge step={2} current={step} label="Quiz" icon={BrainCircuit} onSelect={onStepTap} />
        <StepBadge step={3} current={step} label="Review" icon={ClipboardCheck} onSelect={onStepTap} />
      </div>

      {/* ── error ── */}
      {error && (
        <div className="tsf-error">
          <span>⚠ {error}</span>
          <button onClick={() => setError(null)}>✕</button>
        </div>
      )}

      {/* ────────── STEP 0: CONFIG ────────── */}
      {step === 0 && (
        <div className="tsf-card">
          <h2 className="tsf-card-title">
            <Search size={16} /> Configure Study Run
          </h2>

          <div className="tsf-form">
            <label className="tsf-label">
              Topic
              <input
                id="tsf-topic"
                className="tsf-input"
                placeholder="e.g. eigenvalues, matrix decomposition…"
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
              />
            </label>

            <label className="tsf-label">
              Transcript file
              <select
                id="tsf-transcript"
                className="tsf-input"
                value={transcriptFile}
                onChange={(e) => setTranscriptFile(e.target.value)}
              >
                {transcripts.length === 0 && (
                  <option value="">No transcripts found</option>
                )}
                {transcripts.map((t) => (
                  <option key={t.filename} value={t.filename}>
                    {t.filename}
                  </option>
                ))}
              </select>
            </label>

            <label className="tsf-label">
              Save to folder
              <input
                id="tsf-folder"
                className="tsf-input"
                placeholder="study_flow"
                value={folderPath}
                onChange={(e) => setFolderPath(e.target.value)}
              />
            </label>

            <div className="tsf-row">
              <label className="tsf-label" style={{ flex: 1 }}>
                Quiz questions
                <input
                  id="tsf-quiz-count"
                  className="tsf-input"
                  type="number"
                  min={1}
                  max={20}
                  value={quizCount}
                  onChange={(e) => setQuizCount(Number(e.target.value))}
                />
              </label>
            </div>
          </div>

          <button
            id="tsf-start-btn"
            className="tsf-btn-primary"
            onClick={handleStart}
            disabled={!topic.trim() || !transcriptFile}
          >
            <Zap size={15} /> Start Study Flow
          </button>
        </div>
      )}

      {/* ────────── STEP 1: LOADING ────────── */}
      {step === 1 && loading && (
        <div className="tsf-card tsf-loading-card">
          <Loader2 size={40} className="tsf-spinner" />
          <p className="tsf-loading-title">Building your study package…</p>
          <p className="tsf-loading-sub">
            Retrieving transcript → generating lecture notes → creating quiz deck
          </p>
        </div>
      )}

      {/* ────────── STEP 2: RESULT ────────── */}
      {step === 2 && result && (
        <div className="tsf-results">
          <div className="tsf-result-hero">
            <CheckCircle2 size={32} className="tsf-check-icon" />
            <div>
              <h2 className="tsf-result-title">Study package ready for "{result.topic}"</h2>
              <p className="tsf-result-sub">
                Notes from transcript
                {hitCount > 0 ? ` · ${hitCount} corpus chunk${hitCount !== 1 ? "s" : ""}` : ""}
                {corpusHandoff
                  ? ` · ingested ${corpusHandoff.transcript_chunks ?? 0}+${corpusHandoff.note_chunks ?? 0} chunks`
                  : ""}
                {questionCount > 0 ? ` · ${questionCount} quiz question${questionCount !== 1 ? "s" : ""}` : ""}
              </p>
            </div>
          </div>

          <div className="tsf-result-cards">
            {/* notes card */}
            <div className="tsf-result-card">
              <div className="tsf-result-card-header">
                <BookOpen size={18} />
                <span>Lecture Notes</span>
              </div>
              <p className="tsf-result-card-body">
                Mode: <strong>{result.steps.notes.mode}</strong>
                <br />
                <span className="tsf-path">{notesPath}</span>
              </p>
              <button
                id="tsf-open-notes"
                className="tsf-btn-secondary"
                onClick={() => navigate(`/lecture-notes?file=${encodeURIComponent(notesPath)}`)}
              >
                Open Notes <ChevronRight size={14} />
              </button>
            </div>

            {/* quiz card */}
            <div className="tsf-result-card">
              <div className="tsf-result-card-header">
                <BrainCircuit size={18} />
                <span>Quiz Deck</span>
              </div>
              <p className="tsf-result-card-body">
                {questionCount > 0
                  ? `${questionCount} questions ready`
                  : "No questions generated (LLM offline — template mode)"}
              </p>
              {sessionId ? (
                <button
                  id="tsf-start-quiz"
                  className="tsf-btn-primary"
                  onClick={() => {
                    setStep(3);
                    navigate(`/review?session=${sessionId}`);
                  }}
                >
                  <PlayCircle size={15} /> Start Quiz
                </button>
              ) : (
                <button
                  id="tsf-review-hub"
                  className="tsf-btn-secondary"
                  onClick={() => navigate("/review")}
                >
                  Go to Review Hub <ChevronRight size={14} />
                </button>
              )}
            </div>
          </div>

          {/* reset */}
          <button
            id="tsf-run-again"
            className="tsf-btn-ghost"
            onClick={() => {
              setStep(0);
              setResult(null);
              setError(null);
            }}
          >
            ← Start another flow
          </button>
        </div>
      )}

      {/* ────────── STEP 3: REVIEW ────────── */}
      {step === 3 && (
        <div className="tsf-card tsf-loading-card">
          <ClipboardCheck size={40} className="tsf-check-icon" />
          <p className="tsf-loading-title">Review in progress</p>
          <p className="tsf-loading-sub">
            Complete the quiz in the Review Hub — your results will update the SRS deck automatically.
          </p>
          <button
            className="tsf-btn-secondary"
            onClick={() => navigate("/review")}
          >
            Open Review Hub <ChevronRight size={14} />
          </button>
        </div>
      )}
    </div>
  );
}
