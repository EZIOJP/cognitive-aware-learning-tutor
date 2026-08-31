/**
 * Debounced idle OCR on MathGridCanvas — quiet background recognition of the last line band.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { postMathOcr, type MathOcrResult } from "../../api/mathClient";
import type { MathCanvasHandle } from "./types";
import { lastBandBboxFromMetrics } from "./lastBandBbox";

const IDLE_MS = 1400;
const CONF_SILENCE = 0.45;

type IdleMathOcrOpts = {
  enabled: boolean;
  canvasStamp: string;
  authenticated: boolean;
};

export function useIdleMathOcr(
  canvasRef: React.RefObject<MathCanvasHandle | null>,
  { enabled, canvasStamp, authenticated }: IdleMathOcrOpts,
) {
  const [ocr, setOcr] = useState<MathOcrResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [needsConfirm, setNeedsConfirm] = useState(false);
  const [cropBbox, setCropBbox] = useState<{ x: number; y: number; w: number; h: number } | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const inFlight = useRef(false);

  const run = useCallback(async () => {
    if (!enabled || !authenticated || inFlight.current) return;
    const bridge = canvasRef.current;
    if (!bridge?.hasContent()) return;
    inFlight.current = true;
    setBusy(true);
    try {
      const png = await bridge.exportPng();
      if (!png) return;
      const paths = await bridge.exportPaths();
      const metrics = bridge.exportStrokeMetrics?.() ?? null;
      const crop = lastBandBboxFromMetrics(metrics);
      setCropBbox(crop);
      const result = await postMathOcr(png, {
        paths_json: paths ? JSON.stringify(paths) : undefined,
        stroke_metrics_json: metrics ? JSON.stringify(metrics) : undefined,
        crop_bbox: crop ?? undefined,
        ollama_vision_fallback: false,
      });
      setOcr(result);
      const struct = result.structural_confidence ?? 1;
      const low = result.confidence < CONF_SILENCE || struct < CONF_SILENCE;
      setNeedsConfirm(Boolean(result.latex) && (low || result.needs_review));
    } catch {
      // Quiet — idle OCR must never interrupt thinking.
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }, [authenticated, canvasRef, enabled]);

  useEffect(() => {
    if (!enabled || !canvasStamp) return;
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      void run();
    }, IDLE_MS);
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [canvasStamp, enabled, run]);

  const clear = useCallback(() => {
    setOcr(null);
    setNeedsConfirm(false);
    setCropBbox(null);
  }, []);

  return { ocr, busy, needsConfirm, setNeedsConfirm, clear, runNow: run, cropBbox };
}
