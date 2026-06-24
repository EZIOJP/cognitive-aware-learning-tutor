import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router";
import {
  ArrowLeft,
  Check,
  Loader2,
  Pencil,
  ScanLine,
  SkipForward,
  Target,
} from "lucide-react";
import {
  MathGridCanvas,
  type MathCanvasHandle,
  type StrokeMetricsSnapshot,
} from "../../components/math-canvas";
import { Badge } from "../../app/components/ui/badge";
import { Button } from "../../app/components/ui/button";
import { Card } from "../../app/components/ui/card";
import { Progress } from "../../app/components/ui/progress";
import { useAuth } from "../../context/AuthContext";
import {
  fetchOcrStatus,
  fetchTrainCurriculum,
  postMathOcr,
  submitTrainSample,
  type MathOcrResult,
  type MathOcrStatus,
  type TrainCurriculum,
  type TrainPrompt,
  type TrainTier,
} from "../../api/mathClient";

/** Loose LaTeX normalization for prompt-target comparison (not full CAS equality). */
function normalizeLatex(s: string): string {
  return (s || "")
    .replace(/\s+/g, "")
    .replace(/\\left|\\right/g, "")
    .replace(/\{\}/g, "")
    .toLowerCase();
}

export function TrainPlaygroundPage() {
  const { isAuthenticated } = useAuth();
  const canvasRef = useRef<MathCanvasHandle>(null);
  const [curriculum, setCurriculum] = useState<TrainCurriculum | null>(null);
  const [ocrStatus, setOcrStatus] = useState<MathOcrStatus | null>(null);
  const [tierId, setTierId] = useState<string>("digits");
  const [promptIdx, setPromptIdx] = useState(0);
  const [loading, setLoading] = useState(true);
  const [recognizing, setRecognizing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [predicted, setPredicted] = useState("");
  const [correctLatex, setCorrectLatex] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [lastAgree, setLastAgree] = useState<string | null>(null);
  const [lastOcr, setLastOcr] = useState<MathOcrResult | null>(null);
  const [metrics, setMetrics] = useState<StrokeMetricsSnapshot | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    const data = await fetchTrainCurriculum();
    setCurriculum(data);
    setLoading(false);
  }, []);

  useEffect(() => {
    void refresh();
    void fetchOcrStatus().then(setOcrStatus);
  }, [refresh]);

  const activeTier: TrainTier | undefined = useMemo(
    () => curriculum?.tiers.find((t) => t.id === tierId),
    [curriculum, tierId]
  );

  const activePrompt: TrainPrompt | undefined = activeTier?.prompts[promptIdx];

  // Auto-clear canvas + prediction whenever the active prompt changes.
  useEffect(() => {
    canvasRef.current?.clearAll();
    setPredicted("");
    setCorrectLatex("");
    setLastOcr(null);
  }, [activePrompt?.id]);

  const targetMatch = useMemo(() => {
    if (!predicted || !activePrompt?.target_latex) return null;
    return normalizeLatex(predicted) === normalizeLatex(activePrompt.target_latex);
  }, [predicted, activePrompt?.target_latex]);

  const advancePrompt = useCallback(() => {
    if (!activeTier) return;
    setPromptIdx((i) => {
      const max = (activeTier.prompts.length || 1) - 1;
      return i >= max ? 0 : i + 1;
    });
  }, [activeTier]);

  const handleRecognize = async () => {
    setRecognizing(true);
    setError(null);
    setLastAgree(null);
    try {
      if (!canvasRef.current?.hasContent()) {
        setError("Draw the prompt on the canvas first.");
        return;
      }
      const png = await canvasRef.current?.exportPng();
      if (!png) {
        setError("Canvas export failed — try drawing again.");
        return;
      }
      const paths = await canvasRef.current?.exportPaths();
      const snapshot = canvasRef.current?.exportStrokeMetrics?.() ?? null;
      const result = await postMathOcr(png, {
        paths_json: paths?.length ? JSON.stringify(paths) : undefined,
        stroke_metrics_json: snapshot ? JSON.stringify(snapshot) : undefined,
      });
      setLastOcr(result);
      setPredicted(result.latex);
      setCorrectLatex(result.latex);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Recognize failed");
    } finally {
      setRecognizing(false);
    }
  };

  const saveSample = async (action: "confirm" | "correct") => {
    if (!activePrompt || !activeTier) return;
    setSaving(true);
    setError(null);
    try {
      if (!canvasRef.current?.hasContent()) {
        setError("Draw on the canvas before saving.");
        return;
      }
      const png = await canvasRef.current?.exportPng();
      if (!png) {
        setError("Canvas export failed — try drawing again.");
        return;
      }
      const confirmed = action === "confirm" ? predicted : correctLatex.trim();
      if (action === "correct" && !confirmed) {
        setError("Enter the correct LaTeX before saving.");
        return;
      }
      const paths = await canvasRef.current?.exportPaths();
      const snapshot = canvasRef.current?.exportStrokeMetrics?.() ?? null;
      const out = await submitTrainSample({
        tier: activeTier.id,
        prompt_id: activePrompt.id,
        prompt_text: activePrompt.text,
        canvas_image: png,
        predicted_latex: predicted,
        confirmed_latex: action === "correct" ? confirmed : undefined,
        action,
        paths_json: paths?.length ? JSON.stringify(paths) : undefined,
        stroke_metrics_json: snapshot ? JSON.stringify(snapshot) : undefined,
        target_latex: activePrompt.target_latex,
      });
      if (!out) {
        setError("Could not save sample — sign in and check backend.");
        return;
      }
      setLastAgree(out.agree);
      setPredicted("");
      setCorrectLatex("");
      setLastOcr(null);
      canvasRef.current?.clearAll();
      await refresh();
      // Auto-advance only once this prompt has met its quota
      const samplesAfter = (activePrompt.samples ?? 0) + 1;
      if (samplesAfter >= activePrompt.target_samples) {
        advancePrompt();
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  if (!isAuthenticated) {
    return (
      <div className="p-6 space-y-3">
        <Link to="/math-tutor" className="text-sm text-primary hover:underline inline-flex items-center gap-1">
          <ArrowLeft className="w-4 h-4" /> Math Tutor
        </Link>
        <p className="text-muted-foreground">Sign in to log handwriting training samples.</p>
        <Link to="/login" className="text-primary text-sm hover:underline">Sign in →</Link>
      </div>
    );
  }

  const promptProgress = activePrompt
    ? Math.min(100, (activePrompt.samples / Math.max(1, activePrompt.target_samples)) * 100)
    : 0;

  return (
    <div className="h-full flex flex-col min-h-0 gap-3">
      <div className="flex items-center justify-between gap-2 shrink-0 flex-wrap">
        <div className="flex items-center gap-3">
          <Link
            to="/math-tutor"
            className="inline-flex items-center gap-1 text-sm text-primary hover:underline"
          >
            <ArrowLeft className="w-4 h-4" />
            Math Tutor
          </Link>
          {ocrStatus && (
            <Badge variant={ocrStatus.texteller_available ? "default" : "destructive"}>
              {ocrStatus.texteller_available
                ? "OCR ready"
                : ocrStatus.tier === "ollama_vision"
                  ? "OCR: Ollama fallback"
                  : "OCR not installed"}
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <Button variant="outline" size="sm" onClick={() => void handleRecognize()} disabled={recognizing}>
            {recognizing ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <ScanLine className="w-4 h-4 mr-1" />}
            Recognize
          </Button>
          <Button size="sm" onClick={() => void saveSample("confirm")} disabled={saving || !predicted}>
            <Check className="w-4 h-4 mr-1" />
            Confirm
          </Button>
          <Button variant="secondary" size="sm" onClick={() => void saveSample("correct")} disabled={saving}>
            <Pencil className="w-4 h-4 mr-1" />
            Correct
          </Button>
          <Button variant="ghost" size="sm" onClick={advancePrompt}>
            <SkipForward className="w-4 h-4 mr-1" />
            Skip
          </Button>
        </div>
      </div>

      {curriculum && (
        <p className="text-xs text-muted-foreground shrink-0">
          {curriculum.progress.total_samples} samples · accuracy{" "}
          {(curriculum.progress.accuracy * 100).toFixed(0)}% · retrain in{" "}
          {curriculum.progress.samples_until_retrain} more
          {ocrStatus && !ocrStatus.texteller_available && (
            <span className="text-destructive"> · run scripts\install_ocr.bat to enable OCR</span>
          )}
        </p>
      )}

      <div className="flex-1 flex flex-col lg:flex-row min-h-0 gap-3">
        <Card className="w-full lg:w-56 shrink-0 p-3 overflow-y-auto gloss-panel space-y-2">
          <h2 className="text-sm font-semibold flex items-center gap-1">
            <Target className="w-4 h-4" />
            Curriculum
          </h2>
          {loading && <p className="text-xs text-muted-foreground animate-pulse">Loading…</p>}
          {curriculum?.tiers.map((tier) => (
            <button
              key={tier.id}
              type="button"
              onClick={() => {
                setTierId(tier.id);
                setPromptIdx(0);
              }}
              className={`w-full text-left rounded-lg px-2 py-1.5 text-xs transition-colors ${
                tierId === tier.id ? "bg-primary/15 text-primary font-medium" : "hover:bg-accent/50"
              }`}
            >
              {tier.label}
              <span className="block text-[10px] text-muted-foreground">
                {tier.samples}/{tier.target_samples} samples · {(tier.accuracy * 100).toFixed(0)}%
              </span>
            </button>
          ))}
        </Card>

        <Card className="flex-1 min-h-[400px] flex flex-col overflow-hidden gloss-panel p-0 bg-white">
          <MathGridCanvas
            ref={canvasRef}
            gridCells={activePrompt?.grid_cells ?? 1}
            ghostText={activePrompt?.text ?? ""}
            roughPane
            onMetricsChange={setMetrics}
          />
        </Card>

        <Card className="w-full lg:w-[min(100%,300px)] shrink-0 p-4 flex flex-col gap-3 overflow-y-auto gloss-panel">
          <div>
            <p className="text-xs text-muted-foreground">Draw this prompt</p>
            <p className="text-3xl font-bold mt-1">{activePrompt?.text ?? "—"}</p>
            <p className="text-xs text-muted-foreground mt-1">
              Target LaTeX: <code className="bg-muted px-1 rounded">{activePrompt?.target_latex}</code>
            </p>
            {activePrompt && (
              <div className="mt-2 space-y-1">
                <div className="flex justify-between text-[11px] text-muted-foreground">
                  <span>
                    {activePrompt.samples} / {activePrompt.target_samples} samples
                  </span>
                  <span>
                    {activePrompt.remaining > 0
                      ? `${activePrompt.remaining} more to go`
                      : "quota met ✓"}
                  </span>
                </div>
                <Progress value={promptProgress} className="h-1.5" />
              </div>
            )}
          </div>

          <div className="space-y-2">
            <p className="text-sm font-medium">Prediction</p>
            <p className="font-mono text-sm min-h-[1.5rem]">{predicted || "—"}</p>
            {targetMatch !== null && (
              <Badge variant={targetMatch ? "default" : "destructive"}>
                {targetMatch ? "matches target ✓" : "differs from target"}
              </Badge>
            )}
            {lastOcr && (
              <p className="text-[11px] text-muted-foreground">
                tier {lastOcr.tier} · confidence {(lastOcr.confidence * 100).toFixed(0)}%
              </p>
            )}
            <label className="text-xs text-muted-foreground block">Correct LaTeX (Correct path)</label>
            <input
              value={correctLatex}
              onChange={(e) => setCorrectLatex(e.target.value)}
              className="w-full rounded-lg border border-border/60 bg-background/50 px-2 py-1.5 text-sm font-mono"
              placeholder={activePrompt?.target_latex}
            />
          </div>

          {lastAgree && (
            <Badge variant={lastAgree === "true" || lastAgree === "teacher_match" ? "default" : "secondary"}>
              Saved · {lastAgree}
            </Badge>
          )}
          {error && <p className="text-xs text-destructive">{error}</p>}

          {metrics && metrics.totalStrokes > 0 && (
            <div className="text-[11px] text-muted-foreground space-y-0.5 border-t pt-2">
              <p className="font-medium text-foreground text-xs">Stroke analytics</p>
              <p>
                {metrics.totalStrokes} strokes · {Math.round(metrics.totalInkLengthPx)}px ink ·{" "}
                {(metrics.totalDrawingTimeMs / 1000).toFixed(1)}s
              </p>
              <p>
                cells used {Object.keys(metrics.strokesPerCell).length} · eraser{" "}
                {metrics.eraserEvents}
              </p>
              {Object.entries(metrics.strokesPerCell).map(([cell, n]) => (
                <p key={cell}>
                  cell ({cell}): {n} strokes
                </p>
              ))}
            </div>
          )}

          <p className="text-[10px] text-muted-foreground mt-auto">
            First Recognize after a backend restart takes ~15–20s while the OCR model loads.
          </p>
        </Card>
      </div>
    </div>
  );
}
