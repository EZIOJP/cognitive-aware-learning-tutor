import { useCallback, useState } from "react";
import type { Editor } from "tldraw";
import { postMathIntervention, postMathOcr, type MathInterventionResult, type MathOcrResult } from "../../api/mathClient";

async function editorToDataUrl(editor: Editor): Promise<string | null> {
  const ids = [...editor.getCurrentPageShapeIds()];
  if (!ids.length) return null;
  const { blob } = await editor.toImage(ids, {
    format: "png",
    background: true,
    padding: 24,
    scale: 2,
  });
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onloadend = () => resolve(typeof reader.result === "string" ? reader.result : null);
    reader.readAsDataURL(blob);
  });
}

export function useStudyRoomOcr(editor: Editor | null) {
  const [ocrResult, setOcrResult] = useState<MathOcrResult | null>(null);
  const [hint, setHint] = useState<MathInterventionResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const recognize = useCallback(async () => {
    if (!editor) return;
    setLoading(true);
    setError(null);
    try {
      const png = await editorToDataUrl(editor);
      if (!png) {
        setError("Draw something on the canvas first.");
        return;
      }
      const result = await postMathOcr(png);
      setOcrResult(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Recognize failed");
    } finally {
      setLoading(false);
    }
  }, [editor]);

  const askIntervention = useCallback(async () => {
    if (!editor) return;
    setLoading(true);
    setError(null);
    try {
      const png = await editorToDataUrl(editor);
      if (!png) {
        setError("Draw on the canvas before asking for a hint.");
        return;
      }
      const result = await postMathIntervention({
        canvas_image: png,
        topic: "study room",
        canvas_idle_seconds: 30,
        eraser_events: 0,
      });
      setHint(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ask failed");
    } finally {
      setLoading(false);
    }
  }, [editor]);

  return { ocrResult, hint, loading, error, recognize, askIntervention, clearHint: () => setHint(null) };
}
