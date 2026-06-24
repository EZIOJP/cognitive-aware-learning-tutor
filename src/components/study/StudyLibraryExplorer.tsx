import { useCallback, useMemo, useState } from "react";
import {
  ChevronRight,
  FilePlus,
  FileText,
  Folder,
  FolderOpen,
  FolderPlus,
  LayoutGrid,
  List,
  Sparkles,
  Trash2,
} from "lucide-react";
import { cn } from "../../app/components/ui/utils";
import type { LibraryTree } from "./StudyLibraryTree";
import {
  breadcrumbParts,
  findNodeAt,
  folderOf,
  getDragPath,
  isLibraryDrag,
  setDragPath,
} from "./studyLibraryUtils";

type Selection =
  | { kind: "folder"; path: string }
  | { kind: "file"; path: string }
  | null;

type Props = {
  tree: LibraryTree;
  browsePath: string;
  selectedFile: string;
  comparePaths?: string[];
  onBrowsePath: (path: string) => void;
  onSelectFile: (path: string) => void;
  onToggleCompare?: (path: string) => void;
  onMoveFile?: (path: string, destFolder: string) => void;
  onDeleteFile?: (path: string) => void;
  onDeleteFolder?: (path: string) => void;
  onSummarizeFolder?: (path: string) => void;
  onNewFolder?: () => void;
  onNewFile?: () => void;
  viewMode: "grid" | "list";
  onViewModeChange: (mode: "grid" | "list") => void;
  summarizingFolder?: string;
};

function ExplorerFolderIcon({ open }: { open?: boolean }) {
  return (
    <div className="study-library-explorer-folder-icon">
      {open ? (
        <FolderOpen className="w-10 h-10 text-amber-300 drop-shadow-sm" strokeWidth={1.5} />
      ) : (
        <Folder className="w-10 h-10 text-amber-400 drop-shadow-sm" strokeWidth={1.5} />
      )}
    </div>
  );
}

function ExplorerFileIcon({ kind }: { kind: string }) {
  return (
    <div className="study-library-explorer-file-icon">
      <FileText className="w-9 h-9 text-slate-100" strokeWidth={1.5} />
      <span className="study-library-explorer-file-kind">{kind.slice(0, 4)}</span>
    </div>
  );
}

export function StudyLibraryExplorer({
  tree,
  browsePath,
  selectedFile,
  comparePaths = [],
  onBrowsePath,
  onSelectFile,
  onToggleCompare,
  onMoveFile,
  onDeleteFile,
  onDeleteFolder,
  onSummarizeFolder,
  onNewFolder,
  onNewFile,
  viewMode,
  onViewModeChange,
  summarizingFolder,
}: Props) {
  const [selection, setSelection] = useState<Selection>(null);
  const [dropTarget, setDropTarget] = useState<string | null>(null);

  const current = useMemo(() => findNodeAt(tree, browsePath), [tree, browsePath]);
  const crumbs = useMemo(() => breadcrumbParts(browsePath), [browsePath]);

  const childFolders = current.folders;
  const files = current.files;

  const handleDropOnFolder = useCallback(
    (destFolder: string, e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setDropTarget(null);
      const path = getDragPath(e);
      if (!path || !onMoveFile) return;
      if (folderOf(path) === destFolder) return;
      onMoveFile(path, destFolder);
    },
    [onMoveFile],
  );

  const handleDeleteSelection = () => {
    if (!selection) return;
    if (selection.kind === "file") {
      if (window.confirm("Delete this note?")) onDeleteFile?.(selection.path);
    } else if (selection.kind === "folder") {
      if (window.confirm("Delete this folder and everything inside?")) {
        onDeleteFolder?.(selection.path);
        if (browsePath === selection.path || browsePath.startsWith(`${selection.path}/`)) {
          onBrowsePath("");
        }
      }
    }
    setSelection(null);
  };

  const renderFolderTile = (folder: { path: string; name: string }, inGrid: boolean) => {
    const isSelected = selection?.kind === "folder" && selection.path === folder.path;
    const isDrop = dropTarget === folder.path;

    return (
      <div
        key={folder.path}
        role="button"
        tabIndex={0}
        draggable={false}
        onClick={() => setSelection({ kind: "folder", path: folder.path })}
        onDoubleClick={() => {
          onBrowsePath(folder.path);
          setSelection(null);
        }}
        onDragOver={(e) => {
          if (!isLibraryDrag(e)) return;
          e.preventDefault();
          e.stopPropagation();
          setDropTarget(folder.path);
        }}
        onDragLeave={() => setDropTarget(null)}
        onDrop={(e) => handleDropOnFolder(folder.path, e)}
        className={cn(
          inGrid ? "study-library-explorer-tile" : "study-library-explorer-list-row",
          isSelected && "study-library-explorer-selected",
          isDrop && "study-library-drop-active",
        )}
      >
        <ExplorerFolderIcon open={browsePath === folder.path} />
        <span className="study-library-explorer-label">{folder.name}</span>
      </div>
    );
  };

  const renderFileTile = (file: { relative_path: string; title: string; kind: string }, inGrid: boolean) => {
    const isSelected =
      selection?.kind === "file" && selection.path === file.relative_path;
    const isOpen = selectedFile === file.relative_path;
    const inCompare = comparePaths.includes(file.relative_path);

    return (
      <div
        key={file.relative_path}
        role="button"
        tabIndex={0}
        draggable
        onDragStart={(e) => setDragPath(e, file.relative_path)}
        onClick={(e) => {
          if ((e.ctrlKey || e.metaKey) && onToggleCompare) {
            onToggleCompare(file.relative_path);
            return;
          }
          setSelection({ kind: "file", path: file.relative_path });
          onSelectFile(file.relative_path);
        }}
        onDoubleClick={() => onSelectFile(file.relative_path)}
        title={onToggleCompare ? "Ctrl+click to add to compare" : undefined}
        className={cn(
          inGrid ? "study-library-explorer-tile" : "study-library-explorer-list-row",
          (isSelected || isOpen) && "study-library-explorer-selected",
          inCompare && "study-library-file-compare",
        )}
      >
        <ExplorerFileIcon kind={file.kind} />
        <span className="study-library-explorer-label" title={file.relative_path}>
          {file.title}
        </span>
      </div>
    );
  };

  const gridDropActive = dropTarget === browsePath;

  return (
    <div className="study-library-explorer flex flex-col min-h-0 h-full">
      <div className="study-library-explorer-toolbar">
        <button type="button" className="study-library-explorer-tool" onClick={onNewFolder} title="New folder">
          <FolderPlus className="w-4 h-4" />
          <span>New</span>
        </button>
        <button type="button" className="study-library-explorer-tool" onClick={onNewFile} title="New file">
          <FilePlus className="w-4 h-4" />
          <span>File</span>
        </button>
        <button
          type="button"
          className="study-library-explorer-tool"
          disabled={!selection}
          onClick={handleDeleteSelection}
          title="Delete"
        >
          <Trash2 className="w-4 h-4" />
          <span>Delete</span>
        </button>
        {selection?.kind === "folder" && onSummarizeFolder && (
          <button
            type="button"
            className="study-library-explorer-tool"
            disabled={summarizingFolder === selection.path}
            onClick={() => onSummarizeFolder(selection.path)}
            title="Summarize folder"
          >
            <Sparkles className="w-4 h-4" />
            <span>Summarize</span>
          </button>
        )}
        <div className="ml-auto flex gap-1">
          <button
            type="button"
            className={cn("study-library-explorer-tool-icon", viewMode === "grid" && "active")}
            onClick={() => onViewModeChange("grid")}
            title="Large icons"
          >
            <LayoutGrid className="w-4 h-4" />
          </button>
          <button
            type="button"
            className={cn("study-library-explorer-tool-icon", viewMode === "list" && "active")}
            onClick={() => onViewModeChange("list")}
            title="List"
          >
            <List className="w-4 h-4" />
          </button>
        </div>
      </div>

      <div className="study-library-explorer-address">
        {crumbs.map((c, i) => (
          <span key={c.path} className="flex items-center min-w-0">
            {i > 0 && <ChevronRight className="w-3 h-3 mx-0.5 shrink-0 opacity-50" />}
            <button
              type="button"
              onClick={() => onBrowsePath(c.path)}
              className={cn(
                "truncate hover:underline text-[11px]",
                i === crumbs.length - 1 ? "text-emerald-100" : "text-slate-400",
              )}
            >
              {c.label}
            </button>
          </span>
        ))}
      </div>

      <div className="study-library-explorer-body flex flex-col flex-1 min-h-0">
        <div
          className={cn(
            "study-library-explorer-main flex-1 min-h-0 overflow-y-auto study-library-markdown-scroll",
            gridDropActive && "study-library-drop-active",
          )}
          onDragOver={(e) => {
            if (!isLibraryDrag(e)) return;
            e.preventDefault();
            setDropTarget(browsePath);
          }}
          onDragLeave={() => setDropTarget(null)}
          onDrop={(e) => handleDropOnFolder(browsePath, e)}
        >
          {childFolders.length === 0 && files.length === 0 ? (
            <div className="study-library-explorer-empty">
              <FolderOpen className="w-12 h-12 text-emerald-500/40 mb-2" />
              <p className="text-sm text-slate-400">This folder is empty</p>
              <p className="text-[10px] text-slate-500 mt-1">Drag notes here or create a new file</p>
            </div>
          ) : viewMode === "grid" ? (
            <div className="study-library-explorer-grid">
              {childFolders.map((f) => renderFolderTile(f, true))}
              {files.map((f) => renderFileTile(f, true))}
            </div>
          ) : (
            <div className="study-library-explorer-list">
              {childFolders.map((f) => renderFolderTile(f, false))}
              {files.map((f) => renderFileTile(f, false))}
            </div>
          )}
        </div>

        {comparePaths.length > 0 && (
          <div className="study-library-explorer-compare-hint shrink-0">
            Comparing {comparePaths.length} file{comparePaths.length !== 1 ? "s" : ""} · Ctrl+click to toggle
          </div>
        )}
      </div>
    </div>
  );
}
