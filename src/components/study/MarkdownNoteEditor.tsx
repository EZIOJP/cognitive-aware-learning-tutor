import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import {
  Code2,
  Columns2,
  Eye,
  GitBranch,
  Heading2,
  ImageIcon,
  List,
  Pencil,
  Plus,
  Quote,
  Save,
  Table2,
  X,
} from "lucide-react";
import { Button } from "../../app/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "../../app/components/ui/dropdown-menu";
import { MarkdownNote } from "./MarkdownNote";
import { repairNoteMarkdown } from "./markdownRepair";
import {
  SelectionRegenerateBar,
  SelectionReviewPanel,
  useSelectionRegenerate,
} from "./useSelectionRegenerate";
import { cn } from "../../app/components/ui/utils";

export type NoteEditorLayout = "preview" | "edit" | "split";

type MarkdownNoteEditorProps = {
  content: string;
  onChange: (value: string) => void;
  onSave: () => void | Promise<void>;
  onCancel: () => void;
  saving?: boolean;
  dirty?: boolean;
  snapshotTranscript?: string;
  llmReachable?: boolean;
  onRegenerateSelection?: (opts: {
    selection: string;
    start: number;
    end: number;
    noteMarkdown: string;
    lang: string | null;
  }) => Promise<string>;
};

const SNIPPETS = {
  image: (alt = "Describe this image") => `![${alt}](placeholder:image)\n\n`,
  snapshot: (transcript: string, n = 1) =>
    `![Lecture slide ${n}](/api/transcripts/snapshots/${transcript}/${n}.png)\n\n`,
  mermaid: `\`\`\`mermaid\nflowchart TD\n    A[Concept] --> B[Example]\n    B --> C[Takeaway]\n\`\`\`\n\n`,
  python: `\`\`\`python\n# Runnable in preview (Pyodide)\ndef example():\n    return "hello"\n\nprint(example())\n\`\`\`\n\n`,
  javascript: `\`\`\`javascript\n// Code block\nconsole.log("hello");\n\`\`\`\n\n`,
  heading2: `\n## Section title\n\n`,
  heading3: `\n### Subsection\n\n`,
  bullet: `\n- Key point\n- Another point\n\n`,
  callout: `\n> **Note:** Important idea here.\n\n`,
  table: `\n| Topic | Detail |\n| --- | --- |\n| | |\n\n`,
} as const;

function insertAtCursor(textarea: HTMLTextAreaElement, snippet: string) {
  const start = textarea.selectionStart;
  const end = textarea.selectionEnd;
  const before = textarea.value.slice(0, start);
  const after = textarea.value.slice(end);
  const next = before + snippet + after;
  textarea.value = next;
  const pos = start + snippet.length;
  textarea.setSelectionRange(pos, pos);
  textarea.focus();
  return next;
}

export function MarkdownNoteEditor({
  content,
  onChange,
  onSave,
  onCancel,
  saving = false,
  dirty = false,
  snapshotTranscript,
  llmReachable = false,
  onRegenerateSelection,
}: MarkdownNoteEditorProps) {
  const [layout, setLayout] = useState<NoteEditorLayout>("split");
  const {
    textareaRef,
    syncSelection,
    showSelectionBar,
    selectionText,
    selectionLang,
    selectionExpanded,
    regenerating,
    pending,
    error: selectionError,
    handleRegenerate,
    acceptPending,
    rollbackPending,
  } = useSelectionRegenerate({
    content,
    onChange,
    llmReachable,
    onRegenerate: onRegenerateSelection,
  });

  useEffect(() => {
    textareaRef.current?.focus();
  }, [textareaRef]);

  const insert = useCallback(
    (snippet: string) => {
      const el = textareaRef.current;
      if (!el) {
        onChange(content + snippet);
        return;
      }
      onChange(insertAtCursor(el, snippet));
    },
    [content, onChange],
  );

  const previewContent = useMemo(() => repairNoteMarkdown(content), [content]);

  const toolbar = (
    <div className="flex flex-wrap items-center gap-1.5 border-b border-emerald-900/40 bg-black/25 px-3 py-2">
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button type="button" variant="outline" size="sm" className="h-7 text-xs gap-1">
            <Plus className="h-3.5 w-3.5" />
            Insert
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" className="min-w-[11rem]">
          <DropdownMenuItem onClick={() => insert(SNIPPETS.image())}>
            <ImageIcon className="h-4 w-4 mr-2" /> Image placeholder
          </DropdownMenuItem>
          {snapshotTranscript && (
            <DropdownMenuItem onClick={() => insert(SNIPPETS.snapshot(snapshotTranscript))}>
              <ImageIcon className="h-4 w-4 mr-2 text-amber-400" /> Lecture slide
            </DropdownMenuItem>
          )}
          <DropdownMenuItem onClick={() => insert(SNIPPETS.mermaid)}>
            <GitBranch className="h-4 w-4 mr-2" /> Mermaid diagram
          </DropdownMenuItem>
          <DropdownMenuItem onClick={() => insert(SNIPPETS.python)}>
            <Code2 className="h-4 w-4 mr-2" /> Python block
          </DropdownMenuItem>
          <DropdownMenuItem onClick={() => insert(SNIPPETS.javascript)}>
            <Code2 className="h-4 w-4 mr-2" /> JavaScript block
          </DropdownMenuItem>
          <DropdownMenuItem onClick={() => insert(SNIPPETS.heading2)}>
            <Heading2 className="h-4 w-4 mr-2" /> Heading
          </DropdownMenuItem>
          <DropdownMenuItem onClick={() => insert(SNIPPETS.bullet)}>
            <List className="h-4 w-4 mr-2" /> Bullet list
          </DropdownMenuItem>
          <DropdownMenuItem onClick={() => insert(SNIPPETS.callout)}>
            <Quote className="h-4 w-4 mr-2" /> Callout quote
          </DropdownMenuItem>
          <DropdownMenuItem onClick={() => insert(SNIPPETS.table)}>
            <Table2 className="h-4 w-4 mr-2" /> Table
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <div className="ml-auto flex items-center gap-1">
        <LayoutBtn active={layout === "edit"} onClick={() => setLayout("edit")} icon={<Pencil className="h-3.5 w-3.5" />} />
        <LayoutBtn active={layout === "split"} onClick={() => setLayout("split")} icon={<Columns2 className="h-3.5 w-3.5" />} />
        <LayoutBtn active={layout === "preview"} onClick={() => setLayout("preview")} icon={<Eye className="h-3.5 w-3.5" />} />
        <Button
          type="button"
          size="sm"
          variant="ghost"
          className="h-7 text-xs text-muted-foreground"
          onClick={onCancel}
          disabled={saving}
        >
          <X className="h-3.5 w-3.5 mr-1" />
          Cancel
        </Button>
        <Button
          type="button"
          size="sm"
          className="h-7 text-xs"
          onClick={() => void onSave()}
          disabled={saving || !dirty}
        >
          <Save className="h-3.5 w-3.5 mr-1" />
          {saving ? "Saving…" : "Save"}
        </Button>
      </div>
    </div>
  );

  return (
    <div className="flex flex-col min-h-0 h-full study-note-editor">
      {toolbar}
      <div
        className={cn(
          "flex flex-1 min-h-0",
          layout === "split" && "grid grid-cols-1 lg:grid-cols-2 divide-y lg:divide-y-0 lg:divide-x divide-emerald-900/30",
        )}
      >
        {layout !== "preview" && (
          <div className="flex flex-col min-h-0 min-w-0">
            {layout === "split" && (
              <div className="px-3 py-1 text-[10px] uppercase tracking-wide text-emerald-400/60 border-b border-emerald-900/20">
                Markdown source
              </div>
            )}
            {pending && (
              <SelectionReviewPanel
                pending={pending}
                error={selectionError}
                onAccept={acceptPending}
                onRollback={rollbackPending}
              />
            )}
            {showSelectionBar && (
              <SelectionRegenerateBar
                selectionText={selectionText}
                selectionLang={selectionLang}
                selectionExpanded={selectionExpanded}
                regenerating={regenerating}
                llmReachable={llmReachable}
                error={selectionError}
                onRegenerate={() => void handleRegenerate()}
              />
            )}
            <textarea
              ref={textareaRef}
              value={content}
              onChange={(e) => onChange(e.target.value)}
              onSelect={syncSelection}
              onMouseUp={syncSelection}
              onKeyUp={syncSelection}
              spellCheck={false}
              className="study-note-editor-textarea flex-1 w-full resize-none bg-transparent p-4 font-mono text-[13px] leading-relaxed text-emerald-50/95 outline-none min-h-[280px]"
              aria-label="Edit note markdown"
            />
          </div>
        )}
        {layout !== "edit" && (
          <div className="flex flex-col min-h-0 min-w-0 overflow-hidden">
            {layout === "split" && (
              <div className="px-3 py-1 text-[10px] uppercase tracking-wide text-emerald-400/60 border-b border-emerald-900/20">
                Preview
              </div>
            )}
            <div className="flex-1 overflow-y-auto study-library-markdown-scroll p-4 lg:p-6">
              <MarkdownNote content={previewContent || "_Nothing to preview yet._"} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function LayoutBtn({
  active,
  onClick,
  icon,
}: {
  active: boolean;
  onClick: () => void;
  icon: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "p-1.5 rounded border",
        active
          ? "bg-emerald-500/20 border-emerald-600/50 text-emerald-200"
          : "border-transparent text-muted-foreground hover:bg-muted/30",
      )}
    >
      {icon}
    </button>
  );
}
