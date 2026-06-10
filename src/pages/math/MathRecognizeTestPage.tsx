import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router";
import { ArrowLeft, Loader2, ScanLine } from "lucide-react";
import { TldrawMathCanvas, type MathCanvasHandle } from "../../components/math-canvas";
import { Badge } from "../../app/components/ui/badge";
import { Button } from "../../app/components/ui/button";
import { Card } from "../../app/components/ui/card";
import { useAuth } from "../../context/AuthContext";
import { config } from "../../config";
import { fetchOcrStatus, type MathOcrStatus } from "../../api/mathClient";

interface MathOcrResponse {
  latex: string;
  incomplete_step: boolean;
  confidence: number;
  preprocess_applied: boolean;
}

async function postMathOcr(token: string | null, canvas_image: string): Promise<MathOcrResponse> {
  const headers: HeadersInit = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${config.backend.apiUrl}/api/math/ocr`, {
    method: "POST",
    headers,
    body: JSON.stringify({ canvas_image }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = data.detail;
    const msg =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((d: { msg?: string }) => d.msg).join("; ")
          : `HTTP ${res.status}`;
    throw new Error(msg);
  }
  return data as MathOcrResponse;
}

export function MathRecognizeTestPage() {
  const { token } = useAuth();
  const canvasRef = useRef<MathCanvasHandle>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<MathOcrResponse | null>(null);
  const [shapeCount, setShapeCount] = useState<number | null>(null);
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
    setShapeCount(null);
    try {
      const count = canvasRef.current?.getEditor()?.getCurrentPageShapeIds().size ?? 0;
      setShapeCount(count);
      if (!canvasRef.current?.hasContent()) {
        setError("Nothing to recognize — draw on the canvas first.");
        return;
      }
      const png = await canvasRef.current?.exportPng();
      if (!png) {
        setError("Canvas export failed — try drawing again.");
        return;
      }
      const data = await postMathOcr(token, png);
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
        Draw on the tldraw canvas (grid snap on), then Recognize. First request after a backend
        restart takes ~15–20s while the model loads. Install OCR once with{" "}
        <code className="text-xs bg-muted px-1 rounded">scripts\install_ocr.bat</code>.
      </p>

      <div className="flex-1 flex flex-col lg:flex-row min-h-0 gap-3">
        <Card className="flex-1 min-h-[360px] flex flex-col overflow-hidden gloss-panel p-0">
          <TldrawMathCanvas
            ref={canvasRef}
            persistenceKey="calt-recognize-test"
            showGrid
            onCanvasChange={handleCanvasChange}
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
                {result.preprocess_applied && (
                  <Badge variant="secondary">cropped</Badge>
                )}
              </div>
              <div>
                <p className="text-xs text-muted-foreground mb-1">LaTeX</p>
                <pre className="text-xs font-mono bg-muted/50 rounded-lg p-3 whitespace-pre-wrap break-all">
                  {result.latex || "(empty)"}
                </pre>
              </div>
            </div>
          )}

          {!loading && !error && !result && (
            <p className="text-sm text-muted-foreground">
              Results appear here after you click Recognize.
            </p>
          )}

          {shapeCount !== null && (
            <p className="text-xs text-muted-foreground">Canvas shapes: {shapeCount}</p>
          )}
        </Card>
      </div>
    </div>
  );
}
