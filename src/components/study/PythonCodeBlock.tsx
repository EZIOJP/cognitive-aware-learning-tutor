import { useCallback, useEffect, useState } from "react";
import { Check, Copy, Loader2, Play, RotateCcw } from "lucide-react";
import { runPython } from "./pyodideRunner";
import { useSectionBlockEdit, type SectionBlockHandlers } from "./useSectionBlockEdit";
import { isBrokenBlockContent } from "./noteBlockUtils";

type PythonCodeBlockProps = {
  code: string;
  onCodeChange?: (code: string) => void;
  readOnly?: boolean;
  sectionHandlers?: SectionBlockHandlers;
};

export function PythonCodeBlock({
  code: initialCode,
  onCodeChange,
  readOnly = false,
  sectionHandlers,
}: PythonCodeBlockProps) {
  const handlers = sectionHandlers && !readOnly ? sectionHandlers : undefined;
  const { editing, draft, setDraft, toolbar, localError, displayContent } = useSectionBlockEdit(
    initialCode,
    handlers ? { ...handlers, language: "python" } : undefined,
  );

  const [stdout, setStdout] = useState("");
  const [stderr, setStderr] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [copied, setCopied] = useState(false);

  const source = editing || handlers ? draft : initialCode;
  const showBrokenHint = isBrokenBlockContent(source);

  useEffect(() => {
    setStdout("");
    setStderr("");
    setError(null);
  }, [initialCode]);

  const onCopy = useCallback(async () => {
    await navigator.clipboard.writeText(source);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 2000);
  }, [source]);

  const onReset = useCallback(() => {
    setDraft(initialCode);
    setStdout("");
    setStderr("");
    setError(null);
  }, [initialCode, setDraft]);

  const onRun = useCallback(async () => {
    if (showBrokenHint) {
      setError("Code is empty or invalid — use Fix with AI or edit manually.");
      return;
    }
    setRunning(true);
    setStdout("");
    setStderr("");
    setError(null);
    try {
      const result = await runPython(source);
      setStdout(result.stdout);
      setStderr(result.stderr);
      setError(result.error);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Python runtime failed to load");
    } finally {
      setRunning(false);
    }
  }, [source, showBrokenHint]);

  const hasOutput = Boolean(stdout || stderr || error || localError);

  return (
    <div className="study-python-block my-4 overflow-hidden rounded-lg border border-emerald-900/50 bg-[#0d1117]">
      <div className="flex items-center justify-between gap-2 border-b border-emerald-900/40 bg-emerald-950/40 px-3 py-1.5">
        <span className="text-[10px] uppercase tracking-wide text-emerald-300/70 font-mono">python</span>
        <div className="flex items-center gap-1 flex-wrap justify-end">
          {toolbar}
          <button
            type="button"
            onClick={() => void onRun()}
            disabled={running || (readOnly && !handlers)}
            className="inline-flex items-center gap-1 rounded px-2 py-0.5 text-[10px] text-emerald-100 hover:bg-emerald-900/50 disabled:opacity-50"
          >
            {running ? <Loader2 className="h-3 w-3 animate-spin" /> : <Play className="h-3 w-3" />}
            {running ? "Running…" : "Run"}
          </button>
          <button
            type="button"
            onClick={onReset}
            disabled={running}
            className="inline-flex items-center gap-1 rounded px-2 py-0.5 text-[10px] text-emerald-200/90 hover:bg-emerald-900/50 disabled:opacity-50"
          >
            <RotateCcw className="h-3 w-3" />
            Reset
          </button>
          <button
            type="button"
            onClick={() => void onCopy()}
            className="inline-flex items-center gap-1 rounded px-2 py-0.5 text-[10px] text-emerald-200/90 hover:bg-emerald-900/50"
          >
            {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
            {copied ? "Copied" : "Copy"}
          </button>
        </div>
      </div>

      <textarea
        value={source}
        onChange={(e) => {
          setDraft(e.target.value);
          onCodeChange?.(e.target.value);
        }}
        readOnly={readOnly && !handlers}
        disabled={readOnly && !handlers}
        spellCheck={false}
        placeholder={showBrokenHint ? "# Code missing — click Fix with AI or paste valid Python here" : undefined}
        rows={Math.min(24, Math.max(4, Math.max(source.split("\n").length + 1, showBrokenHint ? 6 : 4)))}
        className="study-python-editor w-full resize-y bg-transparent px-3 py-2 font-mono text-[0.8125rem] leading-relaxed text-emerald-50/95 outline-none border-0"
        aria-label="Python code editor"
      />

      {hasOutput && (
        <div className="border-t border-emerald-900/40 bg-black/40">
          <div className="px-3 py-1 text-[10px] uppercase tracking-wide text-emerald-300/50">Output</div>
          {localError && (
            <pre className="study-python-output study-python-output--error px-3 pb-2 whitespace-pre-wrap">
              {localError}
            </pre>
          )}
          {error && (
            <pre className="study-python-output study-python-output--error px-3 pb-2 whitespace-pre-wrap">{error}</pre>
          )}
          {stdout && <pre className="study-python-output px-3 pb-2 whitespace-pre-wrap">{stdout}</pre>}
          {stderr && (
            <pre className="study-python-output study-python-output--stderr px-3 pb-2 whitespace-pre-wrap">{stderr}</pre>
          )}
        </div>
      )}

      {!hasOutput && !running && (
        <p className="px-3 pb-2 text-[10px] text-emerald-300/40">
          Edit and Run — NumPy/Pandas load automatically on first run (~15MB once for Pyodide + packages).
        </p>
      )}
    </div>
  );
}
