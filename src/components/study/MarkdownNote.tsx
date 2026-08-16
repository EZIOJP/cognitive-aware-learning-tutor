import { Suspense, lazy, useMemo, useRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { prepareNoteMarkdown, listFencedBlocks, normalizeFenceBody } from "../../features/study-notes";
import { extractMarkdownCode } from "./noteBlockUtils";
import { CodeBlock } from "./CodeBlock";
import { StudyMarkdownImage } from "./StudySnapshotImage";
import type { SectionBlockHandlers } from "./useSectionBlockEdit";

const MermaidBlockShell = lazy(() =>
  import("./MermaidBlockShell").then((m) => ({ default: m.MermaidBlockShell })),
);
const PythonCodeBlock = lazy(() =>
  import("./PythonCodeBlock").then((m) => ({ default: m.PythonCodeBlock })),
);

export type MarkdownNoteSectionProps = {
  allowSectionEdit?: boolean;
  llmReachable?: boolean;
  regeneratingBlock?: number | null;
  onBlockSave?: (
    blockIndex: number,
    language: string,
    content: string,
    opts?: { previousContent?: string },
  ) => Promise<void>;
  onBlockRegenerate?: (
    blockIndex: number,
    language: string,
    content: string,
    error?: string,
  ) => Promise<string>;
};

export type NotePreviewMode = "full" | "lite";

type MarkdownNoteProps = {
  content: string;
  sectionEdit?: MarkdownNoteSectionProps;
  /** lite = skip heavy mermaid/python while typing in editor preview */
  previewMode?: NotePreviewMode;
};

function isPythonLang(lang: string | undefined): boolean {
  const l = (lang ?? "").toLowerCase();
  return l === "python" || l === "py";
}

function BlockFallback() {
  return <div className="my-4 h-14 animate-pulse rounded-lg bg-muted/40" aria-hidden />;
}

function sectionHandlersFor(
  blockIndex: number,
  language: string,
  sectionEdit?: MarkdownNoteSectionProps,
): SectionBlockHandlers | undefined {
  if (!sectionEdit?.allowSectionEdit || !sectionEdit.onBlockSave) return undefined;
  return {
    blockIndex,
    language,
    allowSectionEdit: true,
    llmReachable: sectionEdit.llmReachable,
    onBlockSave: sectionEdit.onBlockSave,
    onBlockRegenerate: sectionEdit.onBlockRegenerate,
    regeneratingBlock: sectionEdit.regeneratingBlock,
  };
}

export function MarkdownNote({ content, sectionEdit, previewMode = "full" }: MarkdownNoteProps) {
  const prepared = useMemo(() => prepareNoteMarkdown(content), [content]);
  const fences = useMemo(() => listFencedBlocks(prepared), [prepared]);
  const fenceCursor = useRef(0);
  fenceCursor.current = 0;

  const takeFenceIndex = (lang: string | undefined, code: string): number | undefined => {
    const want = normalizeFenceBody(code);
    const langKey = (lang || "text").toLowerCase();
    const tryFrom = (start: number): number | undefined => {
      for (let i = start; i < fences.length; i++) {
        const fb = fences[i];
        const langOk =
          !lang ||
          fb.lang === langKey ||
          ((langKey === "python" || langKey === "py") && (fb.lang === "python" || fb.lang === "py"));
        if (!langOk) continue;
        if (normalizeFenceBody(fb.content) !== want) continue;
        fenceCursor.current = i + 1;
        return fb.index;
      }
      return undefined;
    };
    return tryFrom(fenceCursor.current) ?? tryFrom(0);
  };

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
          p: ({ node, children }) => {
            const childNodes = node?.children ?? [];
            const onlyImage =
              childNodes.length === 1 &&
              childNodes[0].type === "element" &&
              "tagName" in childNodes[0] &&
              childNodes[0].tagName === "img";
            if (onlyImage) {
              return <div className="my-2">{children}</div>;
            }
            return <p className="text-foreground/90 my-2 leading-7">{children}</p>;
          },
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
          code({ className, children, inline }) {
            const match = /language-(\w+)/.exec(className ?? "");
            const lang = match?.[1];

            if (inline) {
              return (
                <code className="rounded bg-muted px-1 py-0.5 font-mono text-sm">{children}</code>
              );
            }

            const code = extractMarkdownCode(children);
            // Only real ``` fences get indices — indented/extra code nodes must not inflate ordinals.
            const blockIndex = takeFenceIndex(lang, code);
            const handlers =
              blockIndex != null
                ? sectionHandlersFor(blockIndex, lang || "text", sectionEdit)
                : undefined;

            if (lang === "mermaid") {
              if (previewMode === "lite") {
                return (
                  <pre className="my-3 rounded-lg border border-border/60 bg-muted/30 p-3 text-xs text-muted-foreground overflow-x-auto">
                    [Mermaid diagram — pause typing or switch to full preview to render]
                  </pre>
                );
              }
              return (
                <Suspense fallback={<BlockFallback />}>
                  <MermaidBlockShell code={code} sectionHandlers={handlers} />
                </Suspense>
              );
            }
            if (lang && className) {
              if (isPythonLang(lang)) {
                if (previewMode === "lite") {
                  return (
                    <pre className="my-3 rounded-lg border border-border/60 bg-muted/30 p-3 text-xs font-mono overflow-x-auto">
                      {code}
                    </pre>
                  );
                }
                return (
                  <Suspense fallback={<BlockFallback />}>
                    <PythonCodeBlock code={code} sectionHandlers={handlers} />
                  </Suspense>
                );
              }
              return (
                <CodeBlock code={code} language={lang} sectionHandlers={handlers} />
              );
            }
            return (
              <code className="rounded bg-muted px-1 py-0.5 font-mono text-sm">{children}</code>
            );
          },
          pre({ children }) {
            return <>{children}</>;
          },
        }}
      >
        {prepared}
      </ReactMarkdown>
    </div>
  );
}
