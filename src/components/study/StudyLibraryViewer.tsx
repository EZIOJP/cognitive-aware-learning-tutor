import { useCallback, useEffect, useRef, useState } from "react";
import {
  Bookmark,
  ChevronDown,
  FileText,
  Loader2,
  MapPin,
  MoreHorizontal,
  Pencil,
  Play,
  Sparkles,
  Wrench,
} from "lucide-react";
import { MarkdownNote, type MarkdownNoteSectionProps } from "./MarkdownNote";
import { MarkdownNoteEditor } from "./MarkdownNoteEditor";
import { Button } from "../../app/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "../../app/components/ui/dropdown-menu";

type Props = {
  mode: "single" | "compare";
  primaryTitle: string;
  secondaryTitle?: string;
  primaryContent: string;
  secondaryContent?: string;
  loading?: boolean;
  showSyncHeader?: boolean;
  relativePath?: string;
  initialScrollTop?: number;
  bookmarkScrollTop?: number | null;
  onScrollContainer?: (el: HTMLDivElement | null) => void;
  onSetBookmark?: (relativePath: string, scrollTop: number) => void;
  editable?: boolean;
  onSaveContent?: (relativePath: string, content: string) => Promise<void>;
  snapshotTranscript?: string;
  onExport?: (relativePath: string, format: "pdf" | "docx") => Promise<void>;
  onExportFolder?: (folderPath: string, format: "pdf" | "docx") => Promise<void>;
  exportFolderPath?: string;
  onTakeQuiz?: () => void;
  quizReady?: boolean;
  quizLoading?: boolean;
  quizDisabled?: boolean;
  sectionEdit?: MarkdownNoteSectionProps;
  llmReachable?: boolean;
  onRegenerateSelection?: (opts: {
    selection: string;
    start: number;
    end: number;
    noteMarkdown: string;
    lang: string | null;
  }) => Promise<string>;
  onRepairSyntaxOnly?: () => Promise<unknown>;
  onRepairAllBlocks?: () => Promise<unknown>;
};

export function StudyLibraryViewer({
  mode,
  primaryTitle,
  secondaryTitle,
  primaryContent,
  secondaryContent,
  loading,
  showSyncHeader,
  relativePath,
  initialScrollTop = 0,
  bookmarkScrollTop,
  onScrollContainer,
  onSetBookmark,
  editable = false,
  onSaveContent,
  snapshotTranscript,
  onExport,
  onExportFolder,
  exportFolderPath,
  onTakeQuiz,
  quizReady = false,
  quizLoading = false,
  quizDisabled = false,
  sectionEdit,
  llmReachable = false,
  onRegenerateSelection,
  onRepairSyntaxOnly,
  onRepairAllBlocks,
}: Props) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const lastRestoreKeyRef = useRef("");
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(primaryContent);
  const [saving, setSaving] = useState(false);
  const [exporting, setExporting] = useState<"pdf" | "docx" | "folder-pdf" | "folder-docx" | null>(
    null,
  );
  const [repairingAll, setRepairingAll] = useState(false);
  const [repairingSyntax, setRepairingSyntax] = useState(false);

  useEffect(() => {
    if (!editing) setDraft(primaryContent);
  }, [primaryContent, editing]);

  useEffect(() => {
    setEditing(false);
  }, [relativePath]);

  useEffect(() => {
    if (!relativePath || loading || mode !== "single" || !primaryContent || editing) return;
    const key = `${relativePath}:${initialScrollTop}`;
    if (lastRestoreKeyRef.current === key) return;
    lastRestoreKeyRef.current = key;

    let cancelled = false;
    const restore = () => {
      if (cancelled || !scrollRef.current) return;
      scrollRef.current.scrollTop = initialScrollTop;
    };

    requestAnimationFrame(() => {
      requestAnimationFrame(restore);
    });

    return () => {
      cancelled = true;
    };
  }, [relativePath, initialScrollTop, loading, mode, primaryContent, editing]);

  const setScrollContainer = useCallback(
    (el: HTMLDivElement | null) => {
      scrollRef.current = el;
      onScrollContainer?.(el);
    },
    [onScrollContainer],
  );

  const jumpToBookmark = useCallback(() => {
    const el = scrollRef.current;
    if (!el || bookmarkScrollTop == null) return;
    el.scrollTop = bookmarkScrollTop;
  }, [bookmarkScrollTop]);

  const dirty = draft !== primaryContent;

  const handleSave = async () => {
    if (!relativePath || !onSaveContent) return;
    setSaving(true);
    try {
      await onSaveContent(relativePath, draft);
      setEditing(false);
    } finally {
      setSaving(false);
    }
  };

  const runExport = async (
    kind: "pdf" | "docx" | "folder-pdf" | "folder-docx",
  ) => {
    if (editing) return;
    setExporting(kind);
    try {
      if (kind === "pdf" || kind === "docx") {
        if (!relativePath || !onExport) return;
        await onExport(relativePath, kind);
      } else {
        if (exportFolderPath === undefined || !onExportFolder) return;
        await onExportFolder(exportFolderPath, kind === "folder-pdf" ? "pdf" : "docx");
      }
    } finally {
      setExporting(null);
    }
  };

  if (loading) {
    return (
      <section className="study-library-glass flex flex-1 items-center justify-center min-w-0">
        <Loader2 className="w-6 h-6 animate-spin text-emerald-400" />
      </section>
    );
  }

  if (mode === "single") {
    const canExport = relativePath && onExport && !editing && primaryContent;
    const canExportFolder = onExportFolder && exportFolderPath !== undefined && !editing;

    return (
      <section className="study-library-glass flex flex-col flex-1 min-w-0 overflow-hidden">
        <div className="study-library-viewer-header">
          <div className="min-w-0 flex-1">
            <h2 className="study-library-viewer-title truncate">{primaryTitle}</h2>
            {relativePath && (
              <p className="study-library-viewer-path truncate">{relativePath}</p>
            )}
            <p className="text-[10px] mt-0.5">
              <span
                className={
                  llmReachable ? "text-emerald-400/80" : "text-amber-400/90"
                }
              >
                {llmReachable ? "● LLM online" : "● LLM offline — Fix syntax works without AI"}
              </span>
            </p>
          </div>

          {!editing && (
            <div className="flex items-center gap-1 shrink-0">
              {onTakeQuiz && relativePath && primaryContent && (
                <Button
                  type="button"
                  size="sm"
                  variant={quizReady ? "default" : "outline"}
                  className="h-8 text-xs gap-1.5"
                  disabled={quizDisabled || quizLoading}
                  onClick={onTakeQuiz}
                >
                  {quizLoading ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <Play className="w-3.5 h-3.5" />
                  )}
                  {quizReady ? "Take quiz" : "Quiz"}
                </Button>
              )}

              {onRepairSyntaxOnly && relativePath && primaryContent && (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="h-8 text-xs gap-1 border-amber-800/40"
                  disabled={repairingSyntax || repairingAll}
                  title="Fix Mermaid syntax locally (no AI)"
                  onClick={() => {
                    setRepairingSyntax(true);
                    void onRepairSyntaxOnly()
                      .catch(() => undefined)
                      .finally(() => setRepairingSyntax(false));
                  }}
                >
                  {repairingSyntax ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <Wrench className="w-3.5 h-3.5" />
                  )}
                  Fix syntax
                </Button>
              )}

              {onRepairAllBlocks && relativePath && primaryContent && (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="h-8 text-xs gap-1 border-emerald-800/40"
                  disabled={repairingAll || repairingSyntax || !llmReachable}
                  title={
                    llmReachable
                      ? "Fix all broken mermaid/code blocks with Gemma/Ollama"
                      : "Start LM Studio/Ollama (OLLAMA_ENABLED=1)"
                  }
                  onClick={() => {
                    setRepairingAll(true);
                    void onRepairAllBlocks()
                      .catch(() => undefined)
                      .finally(() => setRepairingAll(false));
                  }}
                >
                  {repairingAll ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <Sparkles className="w-3.5 h-3.5" />
                  )}
                  Fix all (AI)
                </Button>
              )}

              {editable && relativePath && onSaveContent && (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="h-8 text-xs"
                  onClick={() => {
                    setDraft(primaryContent);
                    setEditing(true);
                  }}
                >
                  <Pencil className="w-3.5 h-3.5 mr-1" />
                  Edit
                </Button>
              )}

              {(canExport || canExportFolder) && (
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      className="h-8 text-xs gap-1"
                      disabled={!!exporting}
                    >
                      {exporting ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <FileText className="w-3.5 h-3.5" />
                      )}
                      Export
                      <ChevronDown className="w-3 h-3 opacity-60" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end" className="min-w-[10rem]">
                    {canExport && (
                      <>
                        <DropdownMenuItem onClick={() => void runExport("pdf")}>
                          This note as PDF
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => void runExport("docx")}>
                          This note as Word
                        </DropdownMenuItem>
                      </>
                    )}
                    {canExport && canExportFolder && <DropdownMenuSeparator />}
                    {canExportFolder && (
                      <>
                        <DropdownMenuItem onClick={() => void runExport("folder-pdf")}>
                          Folder as PDF
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => void runExport("folder-docx")}>
                          Folder as Word
                        </DropdownMenuItem>
                      </>
                    )}
                  </DropdownMenuContent>
                </DropdownMenu>
              )}

              {relativePath && onSetBookmark && (
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button type="button" variant="ghost" size="icon" className="h-8 w-8">
                      <MoreHorizontal className="w-4 h-4" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem
                      onClick={() => {
                        const top = scrollRef.current?.scrollTop ?? 0;
                        onSetBookmark(relativePath, top);
                      }}
                    >
                      <Bookmark className="w-4 h-4 mr-2" />
                      Save bookmark here
                    </DropdownMenuItem>
                    {bookmarkScrollTop != null && (
                      <DropdownMenuItem onClick={jumpToBookmark}>
                        <MapPin className="w-4 h-4 mr-2" />
                        Jump to bookmark
                      </DropdownMenuItem>
                    )}
                  </DropdownMenuContent>
                </DropdownMenu>
              )}
            </div>
          )}
        </div>

        {editing ? (
          <div className="flex-1 min-h-0 flex flex-col">
            <MarkdownNoteEditor
              content={draft}
              onChange={setDraft}
              onSave={handleSave}
              onCancel={() => {
                setDraft(primaryContent);
                setEditing(false);
              }}
              saving={saving}
              dirty={dirty}
              snapshotTranscript={snapshotTranscript}
              llmReachable={llmReachable}
              onRegenerateSelection={onRegenerateSelection ? onRegenerateSelection : undefined}
            />
          </div>
        ) : (
          <div
            ref={setScrollContainer}
            className="flex-1 overflow-y-auto study-library-markdown-scroll study-library-viewer-body"
          >
            {primaryContent ? (
              <MarkdownNote content={primaryContent} sectionEdit={sectionEdit} />
            ) : (
              <div className="study-library-viewer-empty">
                <FileText className="w-10 h-10 text-emerald-500/40 mb-3" />
                <p className="text-sm font-medium text-emerald-100/90">No note selected</p>
                <p className="text-xs text-muted-foreground mt-1 max-w-xs text-center">
                  Choose a note from the library, or create one from live captions.
                </p>
              </div>
            )}
          </div>
        )}
      </section>
    );
  }

  return (
    <section className="study-library-glass flex flex-col flex-1 min-w-0 overflow-hidden relative">
      {showSyncHeader && (
        <div className="flex items-center justify-center py-2 border-b border-emerald-900/40 text-emerald-400 text-xs gap-2">
          Side-by-side compare
        </div>
      )}
      <div className="flex flex-1 min-h-0 relative">
        <div className="study-library-compare-pane flex-1 flex flex-col min-w-0 border-r border-emerald-900/30">
          <div className="px-4 py-2 border-b border-emerald-900/30 bg-black/20 text-xs font-medium text-slate-300 truncate">
            {primaryTitle}
          </div>
          <div className="flex-1 overflow-y-auto study-library-markdown-scroll study-library-viewer-body">
            <MarkdownNote content={primaryContent || "_No content._"} sectionEdit={sectionEdit} />
          </div>
        </div>
        <div className="study-library-sync-badge absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-10 rounded-full w-8 h-8 flex items-center justify-center shadow-lg" />
        <div className="flex-1 flex flex-col min-w-0">
          <div className="px-4 py-2 border-b border-emerald-900/30 bg-black/20 text-xs font-medium text-slate-300 truncate">
            {secondaryTitle ?? "Reference"}
          </div>
          <div className="flex-1 overflow-y-auto study-library-markdown-scroll study-library-viewer-body">
            <MarkdownNote content={secondaryContent || "_No content._"} />
          </div>
        </div>
      </div>
    </section>
  );
}
