import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router";
import { ArrowLeft, Loader2, ScanLine } from "lucide-react";
import { MathGridCanvas, type MathCanvasHandle, type StrokeMetricsSnapshot } from "../../components/math-canvas";
import { Badge } from "../../app/components/ui/badge";
import { Button } from "../../app/components/ui/button";
import { Card } from "../../app/components/ui/card";
import {
  fetchOcrStatus,
  postMathOcr,
  type MathOcrResult,
  type MathOcrStatus,
} from "../../api/mathClient";

export function MathRecognizeTestPage() {
  const canvasRef = useRef<MathCanvasHandle>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<MathOcrResult | null>(null);
  const [metrics, setMetrics] = useState<StrokeMetricsSnapshot | null>(null);
  const [ocrStatus, setOcrStatus] = useState<MathOcrStatus | null>(null);

  useEffect(() => {
    void fetchOcrStatus().then(setOcrStatus);
  }, []);

  const handleCanvasChange = useCallback(() => {
    setError(null);
  }, []);

  const handleRecognize = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      if (!canvasRef.current?.hasContent()) {
        setError("Nothing to recognize — draw on the canvas first.");
        return;
      }
      const png = await canvasRef.current?.exportPng();
      if (!png) {
        setError("Canvas export failed — try drawing again.");
        return;
      }
      const paths = await canvasRef.current?.exportPaths();
      const snapshot = canvasRef.current?.exportStrokeMetrics?.() ?? null;
      const data = await postMathOcr(png, {
        paths_json: paths?.length ? JSON.stringify(paths) : undefined,
        stroke_metrics_json: snapshot ? JSON.stringify(snapshot) : undefined,
      });
      setResult(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Recognition failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="h-full flex flex-col min-h-0 gap-3">
      <div className="flex items-center justify-between gap-2 shrink-0">
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
              {ocrStatus.texteller_available ? "OCR ready" : "OCR not installed"}
            </Badge>
          )}
        </div>
        <Button onClick={handleRecognize} disabled={loading}>
          {loading ? (
            <Loader2 className="w-4 h-4 animate-spin mr-2" />
          ) : (
            <ScanLine className="w-4 h-4 mr-2" />
          )}
          Recognize
        </Button>
      </div>

      <p className="text-sm text-muted-foreground shrink-0">
        Draw on the grid canvas (pen/eraser, fixed view — no zoom), then Recognize. First request
        after a backend restart takes ~15–20s while the model loads. Install OCR once with{" "}
        <code className="text-xs bg-muted px-1 rounded">scripts\install_ocr.bat</code>.
      </p>

      <div className="flex-1 flex flex-col lg:flex-row min-h-0 gap-3">
        <Card className="flex-1 min-h-[360px] flex flex-col overflow-hidden gloss-panel p-0">
          <MathGridCanvas
            ref={canvasRef}
            onCanvasChange={handleCanvasChange}
            onMetricsChange={setMetrics}
          />
        </Card>

        <Card className="w-full lg:w-[min(100%,320px)] shrink-0 p-4 flex flex-col gap-3 overflow-y-auto">
          <h2 className="text-sm font-semibold">Recognition result</h2>

          {loading && (
            <p className="text-sm text-muted-foreground flex items-center gap-2">
              <Loader2 className="w-4 h-4 animate-spin" />
              Running OCR (first run may download the model)…
            </p>
          )}

          {error && (
            <div className="text-sm text-destructive border border-destructive/30 rounded-lg p-3">
              {error}
            </div>
          )}

          {result && !loading && (
            <div className="space-y-3">
              <div className="flex flex-wrap gap-2">
                <Badge variant={result.incomplete_step ? "destructive" : "default"}>
                  {result.incomplete_step ? "Incomplete step" : "Complete"}
                </Badge>
                <Badge variant="outline">
                  confidence {(result.confidence * 100).toFixed(0)}%
                </Badge>
                <Badge variant="secondary">tier: {result.tier}</Badge>
                {result.preprocess_applied && <Badge variant="secondary">cropped</Badge>}
              </div>
              <div>
                <p className="text-xs text-muted-foreground mb-1">LaTeX</p>
                <pre className="text-xs font-mono bg-muted/50 rounded-lg p-3 whitespace-pre-wrap break-all">
                  {result.latex || "(empty)"}
                </pre>
              </div>
              {result.teacher_latex && (
                <p className="text-xs text-muted-foreground">
                  Teacher: <code className="bg-muted px-1 rounded">{result.teacher_latex}</code>
                </p>
              )}
            </div>
          )}

          {!loading && !error && !result && (
            <p className="text-sm text-muted-foreground">
              Results appear here after you click Recognize.
            </p>
          )}

          {metrics && metrics.totalStrokes > 0 && (
            <div className="text-xs text-muted-foreground space-y-1 border-t pt-2">
              <p className="font-medium text-foreground">Stroke analytics</p>
              <p>
                {metrics.totalStrokes} strokes · {Math.round(metrics.totalInkLengthPx)}px ink ·{" "}
                {(metrics.totalDrawingTimeMs / 1000).toFixed(1)}s drawing
              </p>
              <p>
                cells used: {Object.keys(metrics.strokesPerCell).length} · eraser:{" "}
                {metrics.eraserEvents}
              </p>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
