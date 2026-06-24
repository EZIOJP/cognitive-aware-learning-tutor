import { useCallback, useEffect, useRef, useState } from "react";
import { Check, Loader2, RotateCcw, Sparkles } from "lucide-react";
import { Button } from "../../app/components/ui/button";
import { cn } from "../../app/components/ui/utils";
import { expandSelectionToFencedBlock } from "./noteBlockUtils";

export type SelectionRegenerateState = {
  start: number;
  end: number;
  original: string;
  proposed: string;
};

type UseSelectionRegenerateOptions = {
  content: string;
  onChange: (value: string) => void;
  llmReachable?: boolean;
  onRegenerate?: (opts: {
    selection: string;
    start: number;
    end: number;
    noteMarkdown: string;
    lang: string | null;
  }) => Promise<string>;
};

const MIN_SELECTION = 8;

export function useSelectionRegenerate({
  content,
  onChange,
  llmReachable = false,
  onRegenerate,
}: UseSelectionRegenerateOptions) {
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const [selectionText, setSelectionText] = useState("");
  const [selectionLang, setSelectionLang] = useState<string | null>(null);
  const [selectionExpanded, setSelectionExpanded] = useState(false);
  const [selectionRange, setSelectionRange] = useState<{ start: number; end: number } | null>(null);
  const [regenerating, setRegenerating] = useState(false);
  const [pending, setPending] = useState<SelectionRegenerateState | null>(null);
  const [error, setError] = useState<string | null>(null);

  const syncSelection = useCallback(() => {
    const el = textareaRef.current;
    if (!el || pending) return;
    const start = el.selectionStart;
    const end = el.selectionEnd;
    if (start === end) {
      setSelectionText("");
      setSelectionRange(null);
      setSelectionLang(null);
      setSelectionExpanded(false);
      return;
    }
    const text = el.value.slice(start, end);
    if (text.trim().length < MIN_SELECTION) {
      setSelectionText("");
      setSelectionRange(null);
      setSelectionLang(null);
      setSelectionExpanded(false);
      return;
    }
    const expanded = expandSelectionToFencedBlock(el.value, start, end);
    setSelectionText(expanded.text);
    setSelectionRange({ start: expanded.start, end: expanded.end });
    setSelectionLang(expanded.lang);
    setSelectionExpanded(expanded.expanded);
  }, [pending]);

  const handleRegenerate = useCallback(async () => {
    if (!onRegenerate || !selectionRange || !selectionText.trim()) return;
    if (!llmReachable) {
      setError("LLM offline — start LM Studio/Ollama and set OLLAMA_ENABLED=1.");
      return;
    }
    setRegenerating(true);
    setError(null);
    try {
      const proposed = await onRegenerate({
        selection: selectionText,
        start: selectionRange.start,
        end: selectionRange.end,
        noteMarkdown: content,
        lang: selectionLang,
      });
      if (proposed.trim() === selectionText.trim()) {
        setError("AI returned unchanged text — LLM may be offline or the block needs manual edit.");
      }
      setPending({
        start: selectionRange.start,
        end: selectionRange.end,
        original: selectionText,
        proposed,
      });
      setSelectionText("");
      setSelectionRange(null);
      setSelectionLang(null);
      setSelectionExpanded(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Regeneration failed");
    } finally {
      setRegenerating(false);
    }
  }, [content, llmReachable, onRegenerate, selectionLang, selectionRange, selectionText]);

  const acceptPending = useCallback(() => {
    if (!pending) return;
    const before = content.slice(0, pending.start);
    const after = content.slice(pending.end);
    const next = before + pending.proposed + after;
    onChange(next);
    const pos = pending.start + pending.proposed.length;
    setPending(null);
    setError(null);
    requestAnimationFrame(() => {
      const el = textareaRef.current;
      if (!el) return;
      el.focus();
      el.setSelectionRange(pos, pos);
    });
  }, [content, onChange, pending]);

  const rollbackPending = useCallback(() => {
    const prev = pending;
    setPending(null);
    setError(null);
    if (!prev) return;
    requestAnimationFrame(() => {
      const el = textareaRef.current;
      if (!el) return;
      el.focus();
      el.setSelectionRange(prev.start, prev.end);
    });
  }, [pending]);

  useEffect(() => {
    if (!pending) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") rollbackPending();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [pending, rollbackPending]);

  const showSelectionBar =
    Boolean(onRegenerate) && selectionRange && selectionText && !pending && !regenerating;

  return {
    textareaRef,
    syncSelection,
    showSelectionBar,
    llmReachable,
    selectionText,
    selectionLang,
    selectionExpanded,
    regenerating,
    pending,
    error,
    handleRegenerate,
    acceptPending,
    rollbackPending,
  };
}

type SelectionRegenerateBarProps = {
  selectionText: string;
  selectionLang: string | null;
  selectionExpanded: boolean;
  regenerating: boolean;
  llmReachable?: boolean;
  error: string | null;
  onRegenerate: () => void;
  className?: string;
};

const LLM_OFFLINE_TITLE =
  "LLM offline — start LM Studio/Ollama and set OLLAMA_ENABLED=1.";

export function SelectionRegenerateBar({
  selectionText,
  selectionLang,
  selectionExpanded,
  regenerating,
  llmReachable = false,
  error,
  onRegenerate,
  className,
}: SelectionRegenerateBarProps) {
  const kind =
    selectionLang === "mermaid"
      ? "mermaid diagram"
      : selectionLang && selectionLang !== "text"
        ? `${selectionLang} code`
        : "selection";
  const label =
    selectionLang === "mermaid"
      ? "Fix mermaid"
      : selectionLang
        ? `Fix ${selectionLang}`
        : "Regenerate selection";

  return (
    <div
      className={cn(
        "flex flex-col gap-1 border-b border-emerald-800/40 bg-emerald-950/50",
        className,
      )}
    >
      <div className="flex flex-wrap items-center gap-2 px-3 py-2">
        <span className="text-[11px] text-emerald-300/80">
          {selectionExpanded ? `Expanded to full ${kind}` : `${kind} selected`}
        </span>
        <Button
          type="button"
          size="sm"
          className="h-7 text-xs gap-1"
          disabled={regenerating || !llmReachable}
          title={!llmReachable ? LLM_OFFLINE_TITLE : undefined}
          onClick={onRegenerate}
        >
          {regenerating ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Sparkles className="h-3.5 w-3.5" />
          )}
          {label}
        </Button>
      </div>
      {error && <p className="px-3 pb-2 text-xs text-destructive">{error}</p>}
    </div>
  );
}

type SelectionReviewPanelProps = {
  pending: SelectionRegenerateState;
  error: string | null;
  onAccept: () => void;
  onRollback: () => void;
};

export function SelectionReviewPanel({
  pending,
  error,
  onAccept,
  onRollback,
}: SelectionReviewPanelProps) {
  return (
    <div className="border-b border-amber-800/50 bg-amber-950/30 flex flex-col min-h-0 max-h-[45%]">
      <div className="flex items-center justify-between gap-2 px-3 py-2 border-b border-amber-800/30">
        <span className="text-[11px] font-medium text-amber-200/90">Review AI changes</span>
        <div className="flex items-center gap-1">
          <Button type="button" size="sm" variant="ghost" className="h-7 text-xs" onClick={onRollback}>
            <RotateCcw className="h-3.5 w-3.5 mr-1" />
            Rollback
          </Button>
          <Button type="button" size="sm" className="h-7 text-xs" onClick={onAccept}>
            <Check className="h-3.5 w-3.5 mr-1" />
            Accept changes
          </Button>
        </div>
      </div>
      {error && (
        <p className="px-3 py-1.5 text-xs text-destructive border-b border-amber-800/20">{error}</p>
      )}
      <div className="grid grid-cols-1 md:grid-cols-2 flex-1 min-h-0 divide-y md:divide-y-0 md:divide-x divide-amber-800/20">
        <div className="flex flex-col min-h-0 min-w-0">
          <div className="px-3 py-1 text-[10px] uppercase tracking-wide text-amber-300/60">Original</div>
          <pre className="flex-1 overflow-auto p-3 text-[11px] leading-relaxed font-mono text-amber-100/70 whitespace-pre-wrap m-0">
            {pending.original}
          </pre>
        </div>
        <div className="flex flex-col min-h-0 min-w-0">
          <div className="px-3 py-1 text-[10px] uppercase tracking-wide text-emerald-300/70">Proposed</div>
          <pre className="flex-1 overflow-auto p-3 text-[11px] leading-relaxed font-mono text-emerald-50/95 whitespace-pre-wrap m-0">
            {pending.proposed}
          </pre>
        </div>
      </div>
      <p className="px-3 py-1.5 text-[10px] text-muted-foreground border-t border-amber-800/20">
        Accept replaces the selection in your draft. Rollback or Esc discards the proposal — note is not saved until
        you click Save.
      </p>
    </div>
  );
}
