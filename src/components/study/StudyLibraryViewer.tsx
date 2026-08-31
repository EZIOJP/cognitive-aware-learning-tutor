import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { NoteConflictError } from "../../api/transcriptsClient";
import {
  Bookmark,
  ChevronDown,
  FileText,
  Loader2,
  MapPin,
  Maximize2,
  Minimize2,
  MoreHorizontal,
  Pencil,
  Play,
  Sparkles,
  Wrench,
} from "lucide-react";
import { NoteDocumentView, NoteDocumentEditor, type NoteSectionEditProps } from "../../features/note-renderer";
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
  sectionEdit?: NoteSectionEditProps;
  llmReachable?: boolean;
  llmTier?: string;
  onRegenerateSelection?: (opts: {
    selection: string;
    start: number;
    end: number;
    noteMarkdown: string;
    lang: string | null;
  }) => Promise<string>;
  onRepairSyntaxOnly?: () => Promise<unknown>;
  onRepairAllBlocks?: () => Promise<unknown>;
  /** When set, document title + actions render into this host (page header) instead of the viewer. */
  chromeHost?: HTMLElement | null;
  fullscreen?: boolean;
  onToggleFullscreen?: () => void;
  noteFontStep?: number;
  noteFontMax?: number;
  onNoteFontStep?: (delta: -1 | 1) => void;
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
  llmTier: _llmTier,
  onRegenerateSelection,
  onRepairSyntaxOnly,
  onRepairAllBlocks,
  chromeHost = null,
  fullscreen = false,
  onToggleFullscreen,
  noteFontStep = 3,
  noteFontMax = 6,
  onNoteFontStep,
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
  }, [relativePath, initialScrollTop, loading, mode, editing]);

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
    } catch (e) {
      if (e instanceof NoteConflictError) {
        if (e.message === "reloaded") {
          setEditing(false);
        }
        return;
      }
      console.error(e);
    } finally {
      setSaving(false);
    }
  };

  const runExport = async (kind: "pdf" | "docx" | "folder-pdf" | "folder-docx") => {
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
    const loadingChrome = chromeHost ? (
      <div className="study-library-page-chrome flex items-center gap-2 min-w-0 flex-1">
        <h2 className="text-sm font-semibold text-foreground tracking-wide truncate">
          {primaryTitle}
        </h2>
        {relativePath ? (
          <span className="hidden sm:inline text-[10px] text-muted-foreground truncate">
            {relativePath}
          </span>
        ) : null}
        <span className="text-[10px] text-muted-foreground shrink-0">Loading…</span>
        {onToggleFullscreen ? (
          <Button
            type="button"
            variant={fullscreen ? "secondary" : "outline"}
            size="sm"
            className="h-8 text-xs gap-1.5 ml-auto shrink-0"
            onClick={onToggleFullscreen}
            title={fullscreen ? "Exit fullscreen (Esc)" : "Fullscreen reading"}
            aria-label={fullscreen ? "Exit fullscreen" : "Enter fullscreen"}
          >
            {fullscreen ? <Minimize2 className="w-3.5 h-3.5" /> : <Maximize2 className="w-3.5 h-3.5" />}
            <span className="hidden lg:inline">{fullscreen ? "Exit" : "Full screen"}</span>
          </Button>
        ) : null}
      </div>
    ) : null;
    return (
      <>
        {chromeHost && loadingChrome ? createPortal(loadingChrome, chromeHost) : null}
        <section className="study-library-glass flex flex-1 items-center justify-center min-w-0">
          <Loader2 className="w-6 h-6 animate-spin text-primary" />
        </section>
      </>
    );
  }

  if (mode === "single") {
    const canExport = Boolean(relativePath && onExport && !editing && primaryContent);
    const canExportFolder = Boolean(onExportFolder && exportFolderPath !== undefined && !editing);
    const usePageChrome = Boolean(chromeHost);

    const chrome: ReactNode = (
      <div
        className={
          usePageChrome
            ? "study-library-page-chrome flex items-center gap-3 min-w-0 flex-1"
            : "study-library-viewer-header"
        }
      >
        <div className="min-w-0 flex-1">
          {usePageChrome ? (
            <div className="flex items-center gap-2 min-w-0">
              <h2 className="text-sm font-semibold text-foreground tracking-wide truncate">
                {primaryTitle}
              </h2>
              <span
                className={
                  llmReachable
                    ? "shrink-0 text-[10px] text-primary/80"
                    : "shrink-0 text-[10px] text-amber-400/90"
                }
                title={llmReachable ? "LLM online" : "LLM offline"}
              >
                ●
                <span className="sr-only">{llmReachable ? "Online" : "Offline"}</span>
              </span>
              {relativePath ? (
                <span
                  className="hidden sm:inline text-[10px] text-muted-foreground truncate min-w-0"
                  title={relativePath}
                >
                  {relativePath}
                </span>
              ) : null}
            </div>
          ) : (
            <>
              <h2 className="study-library-viewer-title truncate">{primaryTitle}</h2>
              {relativePath ? (
                <p className="study-library-viewer-path truncate">{relativePath}</p>
              ) : null}
              <p className="text-[10px] mt-0.5">
                <span className={llmReachable ? "text-primary/80" : "text-amber-400/90"}>
                  {llmReachable ? "● LLM online" : "● LLM offline"}
                </span>
              </p>
            </>
          )}
        </div>

        <div className="flex items-center gap-1.5 shrink-0">
          {onToggleFullscreen ? (
            <Button
              type="button"
              variant={fullscreen ? "secondary" : "outline"}
              size="sm"
              className="h-8 text-xs gap-1.5"
              onClick={onToggleFullscreen}
              title={fullscreen ? "Exit fullscreen (Esc)" : "Fullscreen reading"}
              aria-label={fullscreen ? "Exit fullscreen" : "Enter fullscreen"}
              aria-pressed={fullscreen}
            >
              {fullscreen ? (
                <Minimize2 className="w-3.5 h-3.5" />
              ) : (
                <Maximize2 className="w-3.5 h-3.5" />
              )}
              <span className="hidden lg:inline">{fullscreen ? "Exit" : "Full screen"}</span>
            </Button>
          ) : null}
          {onNoteFontStep ? (
            <div className="flex items-center rounded-md border border-border overflow-hidden">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-8 min-w-9 rounded-none px-2 text-xs"
                disabled={noteFontStep <= 0}
                onClick={() => onNoteFontStep(-1)}
                title="Smaller text"
                aria-label="Smaller text"
              >
                A−
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-8 min-w-9 rounded-none px-2 text-sm font-semibold"
                disabled={noteFontStep >= noteFontMax}
                onClick={() => onNoteFontStep(1)}
                title="Larger text"
                aria-label="Larger text"
              >
                A+
              </Button>
            </div>
          ) : null}

          {!editing && onTakeQuiz && relativePath && primaryContent ? (
            <Button
              type="button"
              size="sm"
              variant={quizReady ? "default" : "outline"}
              className="h-8 text-xs gap-1.5"
              disabled={quizDisabled || quizLoading}
              title={
                quizReady
                  ? "Take the generated quiz for this note"
                  : "Generate a quiz draft from this note (does not start the quiz)"
              }
              onClick={onTakeQuiz}
            >
              {quizLoading ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Play className="w-3.5 h-3.5" />
              )}
              <span className="hidden lg:inline">{quizReady ? "Take quiz" : "Quiz"}</span>
            </Button>
          ) : null}

          {!editing && (
            <>

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
                    <span className="hidden sm:inline">Export</span>
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

            {(relativePath && primaryContent && (onRepairSyntaxOnly || onRepairAllBlocks || onSetBookmark)) && (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    title="More note actions"
                    aria-label="More note actions"
                  >
                    {(repairingSyntax || repairingAll) ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <MoreHorizontal className="w-4 h-4" />
                    )}
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="min-w-[12rem]">
                  {onRepairSyntaxOnly && primaryContent && (
                    <DropdownMenuItem
                      disabled={repairingSyntax || repairingAll}
                      onClick={() => {
                        setRepairingSyntax(true);
                        void onRepairSyntaxOnly()
                          .catch(() => undefined)
                          .finally(() => setRepairingSyntax(false));
                      }}
                    >
                      <Wrench className="w-4 h-4 mr-2" />
                      Repair fences
                    </DropdownMenuItem>
                  )}
                  {onRepairAllBlocks && primaryContent && (
                    <DropdownMenuItem
                      disabled={repairingAll || repairingSyntax || !llmReachable}
                      title={
                        llmReachable
                          ? undefined
                          : "Set LLM_API_KEY or start LM Studio"
                      }
                      onClick={() => {
                        setRepairingAll(true);
                        void onRepairAllBlocks()
                          .catch(() => undefined)
                          .finally(() => setRepairingAll(false));
                      }}
                    >
                      <Sparkles className="w-4 h-4 mr-2" />
                      Fix all (AI)
                    </DropdownMenuItem>
                  )}
                  {(onRepairSyntaxOnly || onRepairAllBlocks) && onSetBookmark && (
                    <DropdownMenuSeparator />
                  )}
                  {onSetBookmark && (
                    <DropdownMenuItem
                      onClick={() => {
                        const top = scrollRef.current?.scrollTop ?? 0;
                        onSetBookmark(relativePath, top);
                      }}
                    >
                      <Bookmark className="w-4 h-4 mr-2" />
                      Save bookmark here
                    </DropdownMenuItem>
                  )}
                  {onSetBookmark && bookmarkScrollTop != null && (
                    <DropdownMenuItem onClick={jumpToBookmark}>
                      <MapPin className="w-4 h-4 mr-2" />
                      Jump to bookmark
                    </DropdownMenuItem>
                  )}
                </DropdownMenuContent>
              </DropdownMenu>
            )}
            </>
          )}
        </div>
      </div>
    );

    return (
      <>
        {usePageChrome && chromeHost ? createPortal(chrome, chromeHost) : null}
        <section className="study-library-glass flex flex-col flex-1 min-w-0 overflow-hidden">
          {!usePageChrome ? chrome : null}

          {editing ? (
            <div className="flex-1 min-h-0 flex flex-col">
              <NoteDocumentEditor
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
                <NoteDocumentView content={primaryContent} sectionEdit={sectionEdit} />
              ) : (
                <div className="study-library-viewer-empty">
                  <FileText className="w-10 h-10 text-muted-foreground/40 mb-3" />
                  <p className="text-sm font-medium text-foreground/90">No note selected</p>
                  <p className="text-xs text-muted-foreground mt-1 max-w-xs text-center">
                    Choose a note from the library, or create one from live captions.
                  </p>
                </div>
              )}
            </div>
          )}
        </section>
      </>
    );
  }

  return (
    <section className="study-library-glass flex flex-col flex-1 min-w-0 overflow-hidden relative">
      {showSyncHeader && (
        <div className="flex items-center justify-center py-2 border-b border-border text-primary text-xs gap-2">
          Side-by-side compare
        </div>
      )}
      <div className="flex flex-1 min-h-0 relative">
        <div className="study-library-compare-pane flex-1 flex flex-col min-w-0 border-r border-border">
          <div className="px-4 py-2 border-b border-border bg-muted/40 text-xs font-medium text-muted-foreground truncate">
            {primaryTitle}
          </div>
          <div className="flex-1 overflow-y-auto study-library-markdown-scroll study-library-viewer-body">
            <NoteDocumentView content={primaryContent || "_No content._"} sectionEdit={sectionEdit} />
          </div>
        </div>
        <div className="study-library-sync-badge absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-10 rounded-full w-8 h-8 flex items-center justify-center shadow-lg" />
        <div className="flex-1 flex flex-col min-w-0">
          <div className="px-4 py-2 border-b border-border bg-muted/40 text-xs font-medium text-muted-foreground truncate">
            {secondaryTitle ?? "Reference"}
          </div>
          <div className="flex-1 overflow-y-auto study-library-markdown-scroll study-library-viewer-body">
            <NoteDocumentView content={secondaryContent || "_No content._"} />
          </div>
        </div>
      </div>
    </section>
  );
}
