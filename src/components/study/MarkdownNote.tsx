import { Suspense, lazy, useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { repairMermaidFences } from "./markdownRepair";
import { CodeBlock } from "./CodeBlock";
import { StudyMarkdownImage } from "./StudySnapshotImage";

const MermaidBlock = lazy(() =>
  import("./MermaidBlock").then((m) => ({ default: m.MermaidBlock })),
);
const PythonCodeBlock = lazy(() =>
  import("./PythonCodeBlock").then((m) => ({ default: m.PythonCodeBlock })),
);

type MarkdownNoteProps = {
  content: string;
};

function isPythonLang(lang: string | undefined): boolean {
  const l = (lang ?? "").toLowerCase();
  return l === "python" || l === "py";
}

function BlockFallback() {
  return <div className="my-4 h-14 animate-pulse rounded-lg bg-muted/40" aria-hidden />;
}

export function MarkdownNote({ content }: MarkdownNoteProps) {
  const repaired = useMemo(() => repairMermaidFences(content), [content]);

  return (
    <div className="lecture-notes-markdown space-y-3 text-sm leading-relaxed">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => (
            <h1 className="text-2xl font-bold mt-4 mb-3 text-foreground border-b pb-2">{children}</h1>
          ),
          h2: ({ children }) => (
            <h2 className="text-xl font-semibold mt-6 mb-2 text-foreground">{children}</h2>
          ),
          h3: ({ children }) => (
            <h3 className="text-lg font-medium mt-4 mb-2 text-foreground/95">{children}</h3>
          ),
          ul: ({ children }) => <ul className="list-disc ml-5 space-y-1.5 my-2">{children}</ul>,
          ol: ({ children }) => <ol className="list-decimal ml-5 space-y-1.5 my-2">{children}</ol>,
          p: ({ children }) => <p className="text-foreground/90 my-2 leading-7">{children}</p>,
          blockquote: ({ children }) => (
            <blockquote className="border-l-4 border-emerald-500/60 pl-4 my-3 italic text-foreground/85 bg-muted/20 py-2 rounded-r">
              {children}
            </blockquote>
          ),
          table: ({ children }) => (
            <div className="my-4 overflow-x-auto">
              <table className="min-w-full text-sm border-collapse border border-border">{children}</table>
            </div>
          ),
          th: ({ children }) => (
            <th className="border border-border bg-muted/50 px-3 py-2 text-left font-semibold">{children}</th>
          ),
          td: ({ children }) => <td className="border border-border px-3 py-2">{children}</td>,
          hr: () => <hr className="my-6 border-border/60" />,
          strong: ({ children }) => <strong className="font-semibold text-foreground">{children}</strong>,
          img: ({ src, alt }) => <StudyMarkdownImage src={src} alt={alt} />,
          code({ className, children, ...props }) {
            const match = /language-(\w+)/.exec(className ?? "");
            const lang = match?.[1];
            const code = String(children).replace(/\n$/, "");
            if (lang === "mermaid") {
              return (
                <Suspense fallback={<BlockFallback />}>
                  <MermaidBlock code={code} />
                </Suspense>
              );
            }
            if (lang && className) {
              if (isPythonLang(lang)) {
                return (
                  <Suspense fallback={<BlockFallback />}>
                    <PythonCodeBlock code={code} />
                  </Suspense>
                );
              }
              return <CodeBlock language={lang} code={code} />;
            }
            return (
              <code className="rounded bg-muted px-1 py-0.5 font-mono text-sm" {...props}>
                {children}
              </code>
            );
          },
          pre({ children }) {
            return <>{children}</>;
          },
        }}
      >
        {repaired}
      </ReactMarkdown>
    </div>
  );
}
