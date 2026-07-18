import { useCallback, useEffect, useRef, useState } from "react";
import { Eraser, Loader2, ScanLine } from "lucide-react";
import {
  MathGridCanvas,
  type MathCanvasHandle,
} from "../../components/math-canvas";
import { Button } from "../../app/components/ui/button";
import {
  fetchOcrStatus,
  postMathOcr,
  type MathOcrStatus,
} from "../../api/mathClient";

export type MathQuizOcrMeta = {
  predictedLatex: string;
  canvasImage: string;
  pathsJson?: string;
  strokeMetricsJson?: string;
  confidence: number;
  needsReview: boolean;
};

type Props = {
  disabled?: boolean;
  value: string;
  onChange: (value: string) => void;
  onOcrMetaChange?: (meta: MathQuizOcrMeta | null) => void;
  /** Reset canvas when the question id changes. */
  resetKey?: string;
};

/** Turn common OCR LaTeX into a string SymPy grading can parse. */
export function latexToGradeable(latex: string): string {
  let s = (latex || "").trim();
  if (!s) return "";
  s = s.replace(/^\$+|\$+$/g, "");
  s = s.replace(/\\left|\\right/g, "");
  s = s.replace(/\\times/gi, "*").replace(/\\div/gi, "/").replace(/\\cdot/gi, "*");
  s = s.replace(/\\frac\s*\{([^{}]+)\}\s*\{([^{}]+)\}/g, "($1)/($2)");
  s = s.replace(/\\sqrt\s*\{([^{}]+)\}/g, "sqrt($1)");
  s = s.replace(/[{}]/g, "");
  s = s.replace(/\\\\/g, "");
  s = s.replace(/\s+/g, "");
  return s;
}

/**
 * Handwriting answer pad for math free-text quiz items.
 * Draw → Recognize → edit → parent submits the text string.
 */
export function MathQuizAnswerPanel({
  disabled = false,
  value,
  onChange,
  onOcrMetaChange,
  resetKey,
}: Props) {
  const canvasRef = useRef<MathCanvasHandle>(null);
  const [ocrBusy, setOcrBusy] = useState(false);
  const [ocrError, setOcrError] = useState<string | null>(null);
  const [ocrStatus, setOcrStatus] = useState<MathOcrStatus | null>(null);
  const [lastConfidence, setLastConfidence] = useState<number | null>(null);

  useEffect(() => {
    void fetchOcrStatus().then(setOcrStatus);
  }, []);

  useEffect(() => {
    canvasRef.current?.clearAll();
    setOcrError(null);
    setLastConfidence(null);
    onOcrMetaChange?.(null);
  }, [resetKey]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleRecognize = useCallback(async () => {
    setOcrBusy(true);
    setOcrError(null);
    try {
      if (!canvasRef.current?.hasContent()) {
        setOcrError("Draw your answer on the grid first.");
        return;
      }
      const png = await canvasRef.current.exportPng();
      if (!png) {
        setOcrError("Canvas export failed — try drawing again.");
        return;
      }
      const paths = await canvasRef.current.exportPaths();
      const metrics = canvasRef.current.exportStrokeMetrics?.() ?? null;
      const data = await postMathOcr(png, {
        paths_json: paths?.length ? JSON.stringify(paths) : undefined,
        stroke_metrics_json: metrics ? JSON.stringify(metrics) : undefined,
      });
      const gradeable = latexToGradeable(data.latex) || data.latex.trim();
      onChange(gradeable);
      setLastConfidence(data.confidence);
      onOcrMetaChange?.({
        predictedLatex: data.latex,
        canvasImage: png,
        pathsJson: paths?.length ? JSON.stringify(paths) : undefined,
        strokeMetricsJson: metrics ? JSON.stringify(metrics) : undefined,
        confidence: data.confidence,
        needsReview: data.needs_review,
      });
      if (data.needs_review || data.confidence < 0.55) {
        setOcrError("Low confidence — edit the answer below before Submit.");
      }
    } catch (e) {
      setOcrError(e instanceof Error ? e.message : "Recognition failed");
    } finally {
      setOcrBusy(false);
    }
  }, [onChange, onOcrMetaChange]);

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs text-muted-foreground">
          Write your answer, then Recognize. Edit if OCR is wrong — that trains it.
        </p>
        <div className="flex items-center gap-2">
          {ocrStatus && (
            <span
              className={`text-[10px] uppercase tracking-wide ${
                ocrStatus.texteller_available ? "text-emerald-600" : "text-amber-600"
              }`}
            >
              {ocrStatus.texteller_available ? "OCR ready" : "OCR offline — type below"}
            </span>
          )}
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="h-8 text-xs gap-1"
            disabled={disabled || ocrBusy}
            onClick={() => canvasRef.current?.clearAll()}
          >
            <Eraser className="h-3.5 w-3.5" />
            Clear
          </Button>
          <Button
            type="button"
            size="sm"
            className="h-8 text-xs gap-1"
            disabled={disabled || ocrBusy}
            onClick={() => void handleRecognize()}
          >
            {ocrBusy ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <ScanLine className="h-3.5 w-3.5" />
            )}
            Recognize
          </Button>
        </div>
      </div>

      <div className="min-h-[220px] h-[240px] rounded-lg border border-border overflow-hidden bg-white">
        <MathGridCanvas
          ref={canvasRef}
          roughPane={false}
          onCanvasChange={() => setOcrError(null)}
        />
      </div>

      {ocrError && <p className="text-xs text-amber-600">{ocrError}</p>}

      <label className="text-xs text-muted-foreground">
        Answer (from OCR or typed)
        {lastConfidence != null && (
          <span className="ml-2 text-[10px]">confidence {(lastConfidence * 100).toFixed(0)}%</span>
        )}
      </label>
      <input
        type="text"
        className="w-full rounded-lg border bg-background px-3 py-2 font-mono text-sm"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="e.g. 20 or 1/2"
        disabled={disabled}
        autoComplete="off"
      />
    </div>
  );
}
