/**
 * Shared OCR review UI — per-line LaTeX edit, confidence gate, crop preview, provider badge.
 */
import { useEffect, useState } from "react";
import { AlertTriangle, Check, Loader2 } from "lucide-react";
import { Badge } from "../../app/components/ui/badge";
import { Button } from "../../app/components/ui/button";
import { Input } from "../../app/components/ui/input";
import {
  fetchOcrStatus,
  type MathOcrLine,
  type MathOcrResult,
  type MathOcrStatus,
} from "../../api/mathClient";

const CONF_GATE = 0.55;
const STRUCT_GATE = 0.45;

export type OcrReviewState = {
  latex: string;
  lines: MathOcrLine[];
  confidence: number;
  structuralConfidence: number;
  needsReview: boolean;
  confirmed: boolean;
  cropBbox?: { x: number; y: number; w: number; h: number } | null;
};

type Props = {
  result: MathOcrResult | null;
  busy?: boolean;
  value: string;
  onChange: (value: string) => void;
  onConfirmChange?: (confirmed: boolean) => void;
  cropBbox?: { x: number; y: number; w: number; h: number } | null;
  showProviderBadge?: boolean;
  canvasWidth?: number;
  canvasHeight?: number;
};

export function needsOcrConfirm(result: MathOcrResult | null): boolean {
  if (!result?.latex) return false;
  const struct = result.structural_confidence ?? 1;
  return (
    result.needs_review ||
    result.confidence < CONF_GATE ||
    struct < STRUCT_GATE ||
    result.incomplete_step
  );
}

export function OcrExecutionBadge({ status }: { status: MathOcrStatus | null }) {
  if (!status) return null;
  const provider = status.execution_provider?.replace("ExecutionProvider", "") ?? "CPU";
  const ready = status.texteller_available || status.unimernet_available;
  return (
    <div className="flex flex-wrap items-center gap-1">
      <Badge variant={ready ? "default" : "destructive"} className="text-[10px]">
        {ready ? "OCR ready" : "OCR offline"}
      </Badge>
      {ready && status.execution_provider && (
        <Badge variant="outline" className="text-[10px] uppercase">
          {provider}
        </Badge>
      )}
      {status.engines?.includes("unimernet") && (
        <Badge variant="secondary" className="text-[10px]">
          UniMERNet
        </Badge>
      )}
      {status.finetuned_model && (
        <Badge variant="secondary" className="text-[10px]">
          fine-tuned
        </Badge>
      )}
    </div>
  );
}

export function OcrReviewPanel({
  result,
  busy = false,
  value,
  onChange,
  onConfirmChange,
  cropBbox,
  showProviderBadge = true,
  canvasWidth = 400,
  canvasHeight = 240,
}: Props) {
  const [ocrStatus, setOcrStatus] = useState<MathOcrStatus | null>(null);
  const [lineEdits, setLineEdits] = useState<string[]>([]);
  const [userConfirmed, setUserConfirmed] = useState(false);

  useEffect(() => {
    if (showProviderBadge) void fetchOcrStatus().then(setOcrStatus);
  }, [showProviderBadge]);

  useEffect(() => {
    if (result?.lines?.length) {
      setLineEdits(result.lines.map((l) => l.latex));
    } else if (result?.latex) {
      setLineEdits([result.latex]);
    } else {
      setLineEdits([]);
    }
    setUserConfirmed(false);
    onConfirmChange?.(false);
  }, [result?.latex, result?.lines]); // eslint-disable-line react-hooks/exhaustive-deps

  const gate = needsOcrConfirm(result);
  const struct = result?.structural_confidence ?? 1;

  const applyLineEdits = () => {
    const merged = lineEdits.filter(Boolean).join(" \\\\ ");
    onChange(merged);
  };

  const confirmOcr = () => {
    applyLineEdits();
    setUserConfirmed(true);
    onConfirmChange?.(true);
  };

  const bbox = cropBbox ?? result?.lines?.[result.lines.length - 1]?.bbox;

  return (
    <div className="flex flex-col gap-2">
      {showProviderBadge && (
        <div className="flex items-center justify-between gap-2 flex-wrap">
          <OcrExecutionBadge status={ocrStatus} />
          {busy && (
            <span className="text-xs text-muted-foreground inline-flex items-center gap-1">
              <Loader2 className="h-3 w-3 animate-spin" /> Recognizing…
            </span>
          )}
        </div>
      )}

      {bbox && bbox.w > 0 && bbox.h > 0 && (
        <div className="relative rounded border bg-white overflow-hidden" style={{ height: 48 }}>
          <div
            className="absolute border-2 border-sky-500/70 bg-sky-500/10 pointer-events-none"
            style={{
              left: `${(bbox.x / canvasWidth) * 100}%`,
              top: `${(bbox.y / canvasHeight) * 100}%`,
              width: `${(bbox.w / canvasWidth) * 100}%`,
              height: `${(bbox.h / canvasHeight) * 100}%`,
            }}
            title="OCR crop band"
          />
          <span className="absolute bottom-0 left-1 text-[9px] text-muted-foreground px-1">
            crop preview
          </span>
        </div>
      )}

      {result?.lines && result.lines.length > 1 && (
        <div className="space-y-1">
          <p className="text-xs text-muted-foreground">Per-line OCR (edit if wrong)</p>
          {result.lines.map((line, i) => (
            <div key={i} className="flex items-center gap-2">
              <span className="text-[10px] text-muted-foreground w-4">{i + 1}</span>
              <Input
                className="h-8 font-mono text-xs flex-1"
                value={lineEdits[i] ?? line.latex}
                onChange={(e) => {
                  const next = [...lineEdits];
                  next[i] = e.target.value;
                  setLineEdits(next);
                  onChange(next.filter(Boolean).join(" \\\\ "));
                }}
              />
              <span className="text-[10px] text-muted-foreground whitespace-nowrap">
                {(line.confidence * 100).toFixed(0)}%
              </span>
            </div>
          ))}
        </div>
      )}

      {gate && !userConfirmed && (
        <div className="flex items-start gap-2 rounded-md border border-amber-500/40 bg-amber-500/10 p-2">
          <AlertTriangle className="h-4 w-4 text-amber-600 shrink-0 mt-0.5" />
          <div className="flex-1 text-xs text-amber-800 dark:text-amber-200">
            Low confidence ({((result?.confidence ?? 0) * 100).toFixed(0)}%
            {struct < STRUCT_GATE ? ` · structure ${(struct * 100).toFixed(0)}%` : ""})
            — confirm or edit LaTeX before submit.
          </div>
          <Button type="button" size="sm" variant="outline" className="h-7 text-xs shrink-0" onClick={confirmOcr}>
            <Check className="h-3 w-3 mr-1" />
            Confirm
          </Button>
        </div>
      )}

      {userConfirmed && (
        <p className="text-xs text-emerald-600">OCR confirmed — you can submit.</p>
      )}

      <label className="text-xs text-muted-foreground">
        Answer (LaTeX or typed)
        {result && (
          <span className="ml-2 text-[10px]">
            conf {(result.confidence * 100).toFixed(0)}%
            {result.structural_confidence != null &&
              ` · struct ${(result.structural_confidence * 100).toFixed(0)}%`}
          </span>
        )}
      </label>
      <Input
        className="font-mono text-sm"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="e.g. 20 or \\frac{1}{2}"
      />
    </div>
  );
}

export function canSubmitWithOcr(
  result: MathOcrResult | null,
  userConfirmed: boolean,
  hasHandwriting: boolean,
): boolean {
  if (!hasHandwriting || !result?.latex) return true;
  if (!needsOcrConfirm(result)) return true;
  return userConfirmed;
}
