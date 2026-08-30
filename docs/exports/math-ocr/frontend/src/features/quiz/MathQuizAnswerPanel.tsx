import { useCallback, useEffect, useRef, useState } from "react";
import { Eraser, Loader2, ScanLine } from "lucide-react";
import {
  MathGridCanvas,
  type MathCanvasHandle,
} from "../../components/math-canvas";
import {
  OcrReviewPanel,
  canSubmitWithOcr,
  needsOcrConfirm,
} from "../../components/math-canvas/OcrReviewPanel";
import { lastBandBboxFromMetrics } from "../../components/math-canvas/lastBandBbox";
import { Button } from "../../app/components/ui/button";
import {
  postMathOcr,
  type MathOcrResult,
} from "../../api/mathClient";

export type MathQuizOcrMeta = {
  predictedLatex: string;
  canvasImage: string;
  pathsJson?: string;
  strokeMetricsJson?: string;
  confidence: number;
  needsReview: boolean;
  ocrResult?: MathOcrResult;
};

type Props = {
  disabled?: boolean;
  value: string;
  onChange: (value: string) => void;
  onOcrMetaChange?: (meta: MathQuizOcrMeta | null) => void;
  onOcrConfirmChange?: (confirmed: boolean) => void;
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

export function MathQuizAnswerPanel({
  disabled = false,
  value,
  onChange,
  onOcrMetaChange,
  onOcrConfirmChange,
  resetKey,
}: Props) {
  const canvasRef = useRef<MathCanvasHandle>(null);
  const [ocrBusy, setOcrBusy] = useState(false);
  const [ocrError, setOcrError] = useState<string | null>(null);
  const [ocrResult, setOcrResult] = useState<MathOcrResult | null>(null);
  const [ocrConfirmed, setOcrConfirmed] = useState(false);
  const [cropBbox, setCropBbox] = useState<{ x: number; y: number; w: number; h: number } | null>(null);
  const [hasInk, setHasInk] = useState(false);

  useEffect(() => {
    canvasRef.current?.clearAll();
    setOcrError(null);
    setOcrResult(null);
    setOcrConfirmed(false);
    setCropBbox(null);
    setHasInk(false);
    onOcrMetaChange?.(null);
    onOcrConfirmChange?.(true);
  }, [resetKey]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleRecognize = useCallback(async () => {
    setOcrBusy(true);
    setOcrError(null);
    setOcrConfirmed(false);
    onOcrConfirmChange?.(!needsOcrConfirm(null));
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
      const crop = lastBandBboxFromMetrics(metrics);
      setCropBbox(crop);
      setHasInk(true);
      const data = await postMathOcr(png, {
        paths_json: paths?.length ? JSON.stringify(paths) : undefined,
        stroke_metrics_json: metrics ? JSON.stringify(metrics) : undefined,
        crop_bbox: crop ?? undefined,
      });
      setOcrResult(data);
      const gradeable = latexToGradeable(data.latex) || data.latex.trim();
      onChange(gradeable);
      const needsGate = needsOcrConfirm(data);
      setOcrConfirmed(!needsGate);
      onOcrConfirmChange?.(!needsGate);
      onOcrMetaChange?.({
        predictedLatex: data.latex,
        canvasImage: png,
        pathsJson: paths?.length ? JSON.stringify(paths) : undefined,
        strokeMetricsJson: metrics ? JSON.stringify(metrics) : undefined,
        confidence: data.confidence,
        needsReview: data.needs_review,
        ocrResult: data,
      });
    } catch (e) {
      setOcrError(e instanceof Error ? e.message : "Recognition failed");
    } finally {
      setOcrBusy(false);
    }
  }, [onChange, onOcrMetaChange, onOcrConfirmChange]);

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs text-muted-foreground">
          Write your answer, then Recognize. Edit if OCR is wrong — that trains it.
        </p>
        <div className="flex items-center gap-2">
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
          onCanvasChange={() => {
            setOcrError(null);
            setHasInk(canvasRef.current?.hasContent() ?? false);
          }}
        />
      </div>

      {ocrError && <p className="text-xs text-amber-600">{ocrError}</p>}

      {(ocrResult || ocrBusy) && (
        <OcrReviewPanel
          result={ocrResult}
          busy={ocrBusy}
          value={value}
          onChange={onChange}
          cropBbox={cropBbox}
          canvasWidth={400}
          canvasHeight={240}
          onConfirmChange={(ok) => {
            setOcrConfirmed(ok);
            onOcrConfirmChange?.(canSubmitWithOcr(ocrResult, ok, hasInk));
          }}
        />
      )}

      {!ocrResult && !ocrBusy && (
        <label className="text-xs text-muted-foreground">
          Answer (typed or use Recognize)
          <input
            type="text"
            className="mt-1 w-full rounded-lg border bg-background px-3 py-2 font-mono text-sm"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            placeholder="e.g. 20 or 1/2"
            disabled={disabled}
            autoComplete="off"
          />
        </label>
      )}
    </div>
  );
}

export { canSubmitWithOcr, needsOcrConfirm };
