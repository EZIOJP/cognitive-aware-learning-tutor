import { useCallback, useEffect, useRef, useState } from "react";
import { Bookmark, Download, FileText, Loader2, MapPin, Pencil } from "lucide-react";
import { MarkdownNote } from "./MarkdownNote";
import { MarkdownNoteEditor } from "./MarkdownNoteEditor";
import { cn } from "../../app/components/ui/utils";
import { Button } from "../../app/components/ui/button";

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
}: Props) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const lastRestoreKeyRef = useRef("");
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(primaryContent);
  const [saving, setSaving] = useState(false);
  const [exporting, setExporting] = useState<"pdf" | "docx" | null>(null);

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

  const handleExport = async (format: "pdf" | "docx") => {
    if (!relativePath || !onExport || editing) return;
    setExporting(format);
    try {
      await onExport(relativePath, format);
    } finally {
      setExporting(null);
    }
  };

  const handleExportFolder = async (format: "pdf" | "docx") => {
    if (exportFolderPath === undefined || !onExportFolder || editing) return;
    setExporting(format);
    try {
      await onExportFolder(exportFolderPath, format);
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
    return (
      <section className="study-library-glass flex flex-col flex-1 min-w-0 overflow-hidden">
        <div className="px-4 py-2 border-b border-emerald-900/40 flex items-center gap-2 min-w-0">
          <span className="text-xs font-semibold text-emerald-300/80 truncate flex-1">
            {primaryTitle}
          </span>
          {editable && relativePath && onSaveContent && !editing && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-7 text-[10px] text-emerald-300/90"
              onClick={() => {
                setDraft(primaryContent);
                setEditing(true);
              }}
            >
              <Pencil className="w-3.5 h-3.5 mr-1" />
              Edit
            </Button>
          )}
          {relativePath && onExport && !editing && primaryContent && (
            <>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-7 text-[10px] text-emerald-300/90"
                disabled={!!exporting}
                onClick={() => void handleExport("pdf")}
              >
                {exporting === "pdf" ? (
                  <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" />
                ) : (
                  <Download className="w-3.5 h-3.5 mr-1" />
                )}
                PDF
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-7 text-[10px] text-emerald-300/90"
                disabled={!!exporting}
                onClick={() => void handleExport("docx")}
              >
                {exporting === "docx" ? (
                  <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" />
                ) : (
                  <FileText className="w-3.5 h-3.5 mr-1" />
                )}
                Word
              </Button>
            </>
          )}
          {onExportFolder && exportFolderPath !== undefined && !editing && (
            <>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-7 text-[10px] border-emerald-800/50 text-emerald-200/90"
                disabled={!!exporting}
                title="Export all notes in the current folder as PDF"
                onClick={() => void handleExportFolder("pdf")}
              >
                Folder PDF
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-7 text-[10px] border-emerald-800/50 text-emerald-200/90"
                disabled={!!exporting}
                title="Export all notes in the current folder as Word"
                onClick={() => void handleExportFolder("docx")}
              >
                Folder Word
              </Button>
            </>
          )}
          {!editing && relativePath && onSetBookmark && (
            <button
              type="button"
              title="Bookmark current position"
              onClick={() => {
                const top = scrollRef.current?.scrollTop ?? 0;
                onSetBookmark(relativePath, top);
              }}
              className="p-1 rounded hover:bg-emerald-500/20 text-emerald-400/80"
            >
              <Bookmark className="w-3.5 h-3.5" />
            </button>
          )}
          {!editing && bookmarkScrollTop != null && (
            <button
              type="button"
              title="Jump to bookmark"
              onClick={jumpToBookmark}
              className="p-1 rounded hover:bg-emerald-500/20 text-amber-300/90"
            >
              <MapPin className="w-3.5 h-3.5" />
            </button>
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
            />
          </div>
        ) : (
          <div
            ref={setScrollContainer}
            className="flex-1 overflow-y-auto study-library-markdown-scroll p-6"
          >
            {primaryContent ? (
              <MarkdownNote content={primaryContent} />
            ) : (
              <p className="text-sm text-muted-foreground">
                Select a note from the library, or generate from live captions.
              </p>
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
          Synced Context
        </div>
      )}
      <div className="flex flex-1 min-h-0 relative">
        <div className="study-library-compare-pane flex-1 flex flex-col min-w-0 border-r border-emerald-900/30">
          <div className="px-3 py-2 border-b border-emerald-900/30 bg-black/20 text-[10px] font-semibold text-slate-400 truncate">
            {primaryTitle}
          </div>
          <div className="flex-1 overflow-y-auto study-library-markdown-scroll p-5">
            <MarkdownNote content={primaryContent || "_No content._"} />
          </div>
        </div>
        <div
          className={cn(
            "absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-10",
            "study-library-sync-badge rounded-full w-8 h-8 flex items-center justify-center shadow-lg",
          )}
        />
        <div className="flex-1 flex flex-col min-w-0">
          <div className="px-3 py-2 border-b border-emerald-900/30 bg-black/20 text-[10px] font-semibold text-slate-400 truncate">
            {secondaryTitle ?? "Reference"}
          </div>
          <div className="flex-1 overflow-y-auto study-library-markdown-scroll p-5">
            <MarkdownNote content={secondaryContent || "_No content._"} />
          </div>
        </div>
      </div>
    </section>
  );
}
