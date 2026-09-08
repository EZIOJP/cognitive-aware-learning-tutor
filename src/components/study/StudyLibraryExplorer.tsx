import { useCallback, useEffect, useMemo, useState } from "react";
import { FileText, Folder, FolderOpen } from "lucide-react";
import { cn } from "../../app/components/ui/utils";
import type { LibraryTree } from "./StudyLibraryTree";
import type { LibraryExplorerSelection, LibrarySortMode } from "./studyLibraryUtils";
import {
  findNodeAt,
  folderOf,
  getDragPath,
  isLibraryDrag,
  isOsFileDrag,
  setDragPath,
} from "./studyLibraryUtils";

type Props = {
  tree: LibraryTree;
  browsePath: string;
  selectedFile: string;
  selection: LibraryExplorerSelection;
  onSelectionChange: (selection: LibraryExplorerSelection) => void;
  comparePaths?: string[];
  sortMode?: LibrarySortMode;
  onBrowsePath: (path: string) => void;
  onSelectFile: (path: string) => void;
  onToggleCompare?: (path: string) => void;
  onMoveFile?: (path: string, destFolder: string) => void;
  onImportFiles?: (files: File[], destFolder: string) => void;
  viewMode: "grid" | "list";
  importing?: boolean;
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

function ExplorerFileIcon() {
  return (
    <div className="study-library-explorer-file-icon">
      <FileText className="w-9 h-9 text-slate-100" strokeWidth={1.5} />
    </div>
  );
}

export function StudyLibraryExplorer({
  tree,
  browsePath,
  selectedFile,
  selection,
  onSelectionChange,
  comparePaths = [],
  sortMode = "name-asc",
  onBrowsePath,
  onSelectFile,
  onToggleCompare,
  onMoveFile,
  onImportFiles,
  viewMode,
  importing,
}: Props) {
  const [dropTarget, setDropTarget] = useState<string | null>(null);
  const [osDropActive, setOsDropActive] = useState(false);

  const current = useMemo(() => findNodeAt(tree, browsePath), [tree, browsePath]);

  useEffect(() => {
    if (!selectedFile) return;
    onSelectionChange({ kind: "file", path: selectedFile });
  }, [selectedFile, onSelectionChange]);

  const childFolders = useMemo(() => {
    const folders = [...current.folders];
    folders.sort((a, b) => {
      const cmp = a.name.localeCompare(b.name, undefined, { sensitivity: "base" });
      return sortMode === "name-desc" ? -cmp : cmp;
    });
    return folders;
  }, [current.folders, sortMode]);

  const files = useMemo(() => {
    const list = [...current.files];
    list.sort((a, b) => {
      const cmp = (a.title || a.relative_path).localeCompare(
        b.title || b.relative_path,
        undefined,
        { sensitivity: "base" },
      );
      return sortMode === "name-desc" ? -cmp : cmp;
    });
    return list;
  }, [current.files, sortMode]);

  const clearDropState = useCallback(() => {
    setDropTarget(null);
    setOsDropActive(false);
  }, []);

  const handleDropOnFolder = useCallback(
    (destFolder: string, e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      const osFiles = isOsFileDrag(e) ? Array.from(e.dataTransfer.files || []) : [];
      clearDropState();
      if (osFiles.length && onImportFiles) {
        onImportFiles(osFiles, destFolder);
        return;
      }
      const path = getDragPath(e);
      if (!path || !onMoveFile) return;
      if (folderOf(path) === destFolder) return;
      onMoveFile(path, destFolder);
    },
    [clearDropState, onImportFiles, onMoveFile],
  );

  const allowDropOver = useCallback(
    (e: React.DragEvent, destFolder: string) => {
      if (isOsFileDrag(e) && onImportFiles) {
        e.preventDefault();
        e.stopPropagation();
        e.dataTransfer.dropEffect = "copy";
        setDropTarget(destFolder);
        setOsDropActive(true);
        return;
      }
      if (isLibraryDrag(e)) {
        e.preventDefault();
        e.stopPropagation();
        e.dataTransfer.dropEffect = "move";
        setDropTarget(destFolder);
        setOsDropActive(false);
      }
    },
    [onImportFiles],
  );

  const renderFolderTile = (folder: { path: string; name: string }, inGrid: boolean) => {
    const isSelected = selection?.kind === "folder" && selection.path === folder.path;
    const isDrop = dropTarget === folder.path;

    return (
      <div
        key={folder.path}
        role="button"
        tabIndex={0}
        draggable={false}
        onClick={() => onSelectionChange({ kind: "folder", path: folder.path })}
        onDoubleClick={() => {
          onBrowsePath(folder.path);
          onSelectionChange(null);
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter") onBrowsePath(folder.path);
        }}
        onDragOver={(e) => allowDropOver(e, folder.path)}
        onDragLeave={() => clearDropState()}
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
    const isSelected = selection?.kind === "file" && selection.path === file.relative_path;
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
          onSelectionChange({ kind: "file", path: file.relative_path });
        }}
        onDoubleClick={() => onSelectFile(file.relative_path)}
        onKeyDown={(e) => {
          if (e.key === "Enter") onSelectFile(file.relative_path);
        }}
        title="Double-click to open · Ctrl+click to compare"
        className={cn(
          inGrid ? "study-library-explorer-tile" : "study-library-explorer-list-row",
          (isSelected || isOpen) && "study-library-explorer-selected",
          inCompare && "study-library-file-compare",
        )}
      >
        <ExplorerFileIcon />
        <span className="study-library-explorer-label" title={file.relative_path}>
          {file.title}
        </span>
        {inCompare ? (
          <span className="study-library-explorer-compare-pill" aria-label="In compare">
            cmp
          </span>
        ) : null}
      </div>
    );
  };

  const gridDropActive = dropTarget === browsePath;

  return (
    <div className="study-library-explorer flex flex-col min-h-0 h-full">
      <div className="study-library-explorer-body flex flex-col flex-1 min-h-0">
        <div
          className={cn(
            "study-library-explorer-main flex-1 min-h-0 overflow-y-auto study-library-markdown-scroll relative",
            gridDropActive && "study-library-drop-active",
          )}
          onDragOver={(e) => allowDropOver(e, browsePath)}
          onDragLeave={() => clearDropState()}
          onDrop={(e) => handleDropOnFolder(browsePath, e)}
        >
          {(osDropActive && gridDropActive) || importing ? (
            <div className="study-library-explorer-drop-overlay" aria-live="polite">
              {importing ? "Importing…" : "Drop to import notes"}
            </div>
          ) : null}
          {childFolders.length === 0 && files.length === 0 ? (
            <div className="study-library-explorer-empty">
              <FolderOpen className="w-12 h-12 text-emerald-500/40 mb-2" />
              <p className="text-sm text-slate-400">No notes here yet</p>
              <p className="text-[10px] text-slate-500 mt-1">Use New or Import in the toolbar above</p>
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

        {comparePaths.length > 0 ? (
          <div className="study-library-explorer-compare-hint shrink-0">
            Comparing {comparePaths.length} note{comparePaths.length !== 1 ? "s" : ""} · Ctrl+click to toggle
          </div>
        ) : selection ? (
          <div className="study-library-explorer-selection-hint shrink-0">
            <span className="truncate">{selection.path.split("/").pop()}</span>
            <span className="text-muted-foreground">· double-click to open</span>
          </div>
        ) : null}
      </div>
    </div>
  );
}
