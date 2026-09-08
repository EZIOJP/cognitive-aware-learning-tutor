import { Suspense, lazy, useMemo, useRef, isValidElement, type ReactElement, type ReactNode } from "react";
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

const TOPIC_ID_RE = /^L\d+-T\d+$/i;
const DASH_SEP_RE = /\s*[—–-]\s*/g;

function flattenText(node: ReactNode): string {
  if (node == null || typeof node === "boolean") return "";
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(flattenText).join("");
  if (isValidElement(node)) return flattenText((node as ReactElement<{ children?: ReactNode }>).props.children);
  return "";
}

function stripLeadingDash(text: string): string {
  return text.replace(/^\s*[—–-]\s*/, "");
}

function normalizeDashes(text: string): string {
  return text.replace(DASH_SEP_RE, " ").replace(/\s{2,}/g, " ").trim();
}

function cleanTopicTitleChildren(nodes: ReactNode[]): ReactNode[] {
  const out: ReactNode[] = [];
  let strippedLead = false;
  for (const node of nodes) {
    if (!strippedLead && typeof node === "string") {
      const t = normalizeDashes(stripLeadingDash(node));
      if (t) out.push(t);
      strippedLead = true;
      continue;
    }
    if (typeof node === "string") {
      const t = normalizeDashes(node);
      if (t) out.push(t);
      continue;
    }
    out.push(node);
  }
  return out;
}

function TopicHeading({ children, topicId }: { children?: ReactNode; topicId?: string | null }) {
  const nodes = Array.isArray(children) ? children : children != null ? [children] : [];
  const first = nodes[0];
  let resolvedId = topicId ?? null;
  let titleNodes = nodes;

  if (!resolvedId && isValidElement(first) && first.type === "code") {
    const codeText = flattenText(first.props.children).trim();
    if (TOPIC_ID_RE.test(codeText)) {
      resolvedId = codeText.toUpperCase();
      titleNodes = nodes.slice(1);
    }
  }

  if (!resolvedId) {
    const text = flattenText(children).trim();
    const m = text.match(/^`?(L\d+-T\d+)`?\s*[—–-]\s*(.+)$/i);
    if (m) {
      resolvedId = m[1].toUpperCase();
      const title = normalizeDashes(m[2]);
      return (
        <div className="lecture-topic-heading-wrap">
          <h2 className="lecture-topic-heading">
            <span className="topic-id-badge">{resolvedId}</span>
            <span className="lecture-topic-title">{title}</span>
          </h2>
        </div>
      );
    }
    return <h2 className="lecture-section-heading">{children}</h2>;
  }

  return (
    <div className="lecture-topic-heading-wrap">
      <h2 className="lecture-topic-heading">
        <span className="topic-id-badge">{resolvedId}</span>
        <span className="lecture-topic-title">{cleanTopicTitleChildren(titleNodes)}</span>
      </h2>
    </div>
  );
}

const TOPIC_H2_LINE_RE = /^## `?(L\d+-T\d+)`?\s*[—–-]\s*.+$/i;

function splitNoteIntoSections(markdown: string): { lead: string; topics: string[] } {
  const lines = markdown.split("\n");
  const topicStarts: number[] = [];
  for (let i = 0; i < lines.length; i++) {
    if (TOPIC_H2_LINE_RE.test(lines[i])) topicStarts.push(i);
  }
  if (!topicStarts.length) return { lead: markdown, topics: [] };

  const lead = lines.slice(0, topicStarts[0]).join("\n").trim();
  const topics = topicStarts.map((start, idx) => {
    const end = idx + 1 < topicStarts.length ? topicStarts[idx + 1] : lines.length;
    return lines.slice(start, end).join("\n").trim();
  });
  return { lead, topics };
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
  const sections = useMemo(() => splitNoteIntoSections(prepared), [prepared]);
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

  const markdownComponents = {
    h1: ({ children }: { children?: ReactNode }) => (
      <h1 className="lecture-doc-title">{children}</h1>
    ),
    h2: ({ children }: { children?: ReactNode }) => <TopicHeading>{children}</TopicHeading>,
    h3: ({ children }: { children?: ReactNode }) => (
      <h3 className="lecture-subheading">{children}</h3>
    ),
    ul: ({ children }: { children?: ReactNode }) => (
      <ul className="lecture-list lecture-list--unordered">{children}</ul>
    ),
    ol: ({ children }: { children?: ReactNode }) => (
      <ol className="lecture-list lecture-list--ordered">{children}</ol>
    ),
    p: ({ node, children }: { node?: { children?: unknown[] }; children?: ReactNode }) => {
      const childNodes = node?.children ?? [];
      const onlyImage =
        childNodes.length === 1 &&
        childNodes[0] != null &&
        typeof childNodes[0] === "object" &&
        "type" in childNodes[0] &&
        childNodes[0].type === "element" &&
        "tagName" in childNodes[0] &&
        childNodes[0].tagName === "img";
      if (onlyImage) {
        return <div className="lecture-figure">{children}</div>;
      }
      return <p className="lecture-paragraph">{children}</p>;
    },
    blockquote: ({ children }: { children?: ReactNode }) => (
      <blockquote className="lecture-callout">{children}</blockquote>
    ),
    table: ({ children }: { children?: ReactNode }) => (
      <div className="lecture-table-wrap">
        <table className="lecture-table">{children}</table>
      </div>
    ),
    th: ({ children }: { children?: ReactNode }) => <th className="lecture-table-th">{children}</th>,
    td: ({ children }: { children?: ReactNode }) => <td className="lecture-table-td">{children}</td>,
    hr: () => <hr className="lecture-divider" />,
    strong: ({ children }: { children?: ReactNode }) => (
      <strong className="font-semibold text-foreground">{children}</strong>
    ),
    img: ({ src, alt }: { src?: string; alt?: string }) => <StudyMarkdownImage src={src} alt={alt} />,
    code({
      className,
      children,
      inline,
    }: {
      className?: string;
      children?: ReactNode;
      inline?: boolean;
    }) {
      const match = /language-(\w+)/.exec(className ?? "");
      const lang = match?.[1];

      if (inline) {
        return <code className="lecture-inline-code">{children}</code>;
      }

      const code = extractMarkdownCode(children);
      const blockIndex = takeFenceIndex(lang, code);
      const handlers =
        blockIndex != null ? sectionHandlersFor(blockIndex, lang || "text", sectionEdit) : undefined;

      if (lang === "mermaid") {
        if (previewMode === "lite") {
          return (
            <pre className="lecture-lite-fence">
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
            return <pre className="lecture-lite-fence lecture-lite-fence--mono">{code}</pre>;
          }
          return (
            <Suspense fallback={<BlockFallback />}>
              <PythonCodeBlock code={code} sectionHandlers={handlers} />
            </Suspense>
          );
        }
        return <CodeBlock code={code} language={lang} sectionHandlers={handlers} />;
      }
      return <code className="lecture-inline-code">{children}</code>;
    },
    pre({ children }: { children?: ReactNode }) {
      return <>{children}</>;
    },
  };

  const renderMarkdown = (chunk: string) => (
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
      {chunk}
    </ReactMarkdown>
  );

  const hasTopicSections = sections.topics.length > 0;

  return (
    <div className="lecture-notes-markdown">
      {hasTopicSections ? (
        <>
          {sections.lead ? <div className="lecture-notes-lead">{renderMarkdown(sections.lead)}</div> : null}
          <div className="lecture-topic-stack">
            {sections.topics.map((topic, index) => (
              <section key={index} className="lecture-topic-section" aria-label={`Topic section ${index + 1}`}>
                {renderMarkdown(topic)}
              </section>
            ))}
          </div>
        </>
      ) : (
        renderMarkdown(prepared)
      )}
    </div>
  );
}
