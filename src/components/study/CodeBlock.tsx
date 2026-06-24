import { useCallback, useState } from "react";
import { Check, Copy } from "lucide-react";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";

type CodeBlockProps = {
  code: string;
  language: string;
};

export function CodeBlock({ code, language }: CodeBlockProps) {
  const [copied, setCopied] = useState(false);
  const lang = language.toLowerCase();

  const onCopy = useCallback(async () => {
    await navigator.clipboard.writeText(code);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 2000);
  }, [code]);

  return (
    <div className="study-code-block my-4 overflow-hidden rounded-lg border border-emerald-900/50 bg-[#0d1117]">
      <div className="flex items-center justify-between gap-2 border-b border-emerald-900/40 bg-emerald-950/40 px-3 py-1.5">
        <span className="text-[10px] uppercase tracking-wide text-emerald-300/70 font-mono">{lang}</span>
        <button
          type="button"
          onClick={() => void onCopy()}
          className="inline-flex items-center gap-1 rounded px-2 py-0.5 text-[10px] text-emerald-200/90 hover:bg-emerald-900/50"
        >
          {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
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
        {code}
      </SyntaxHighlighter>
    </div>
  );
}
