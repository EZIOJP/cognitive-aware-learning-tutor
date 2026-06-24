import { useCallback, useState } from "react";
import { Check, Copy } from "lucide-react";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import { useSectionBlockEdit, type SectionBlockHandlers } from "./useSectionBlockEdit";
import { isBrokenBlockContent } from "./noteBlockUtils";

type CodeBlockProps = {
  code: string;
  language: string;
  sectionHandlers?: SectionBlockHandlers;
};

export function CodeBlock({ code, language, sectionHandlers }: CodeBlockProps) {
  const lang = language.toLowerCase();
  const { editing, draft, setDraft, toolbar, localError, displayContent } = useSectionBlockEdit(
    code,
    sectionHandlers ? { ...sectionHandlers, language: lang } : undefined,
  );

  const [copied, setCopied] = useState(false);

  const onCopy = useCallback(async () => {
    await navigator.clipboard.writeText(displayContent);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 2000);
  }, [displayContent]);

  const showBrokenHint = isBrokenBlockContent(displayContent);

  return (
    <div className="study-code-block my-4 overflow-hidden rounded-lg border border-emerald-900/50 bg-[#0d1117]">
      <div className="flex items-center justify-between gap-2 border-b border-emerald-900/40 bg-emerald-950/40 px-3 py-1.5">
        <span className="text-[10px] uppercase tracking-wide text-emerald-300/70 font-mono">{lang}</span>
        <div className="flex items-center gap-1">
          {toolbar}
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

      {editing ? (
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          spellCheck={false}
          rows={Math.min(24, Math.max(4, draft.split("\n").length + 1))}
          className="study-python-editor w-full resize-y bg-transparent px-3 py-2 font-mono text-[0.8125rem] leading-relaxed text-emerald-50/95 outline-none border-0"
          aria-label={`Edit ${lang} code`}
        />
      ) : showBrokenHint ? (
        <pre className="px-3 py-2 text-[0.8125rem] text-amber-200/80 font-mono">
          Code block is empty or invalid — use Fix with AI.
        </pre>
      ) : (
        <SyntaxHighlighter
          language={lang === "py" ? "python" : lang}
          style={oneDark}
          customStyle={{
            margin: 0,
            padding: "12px 14px",
            background: "transparent",
            fontSize: "0.8125rem",
            lineHeight: 1.55,
          }}
          showLineNumbers
          wrapLongLines
        >
          {displayContent}
        </SyntaxHighlighter>
      )}

      {localError && (
        <p className="px-3 pb-2 text-xs text-destructive">{localError}</p>
      )}
    </div>
  );
}
