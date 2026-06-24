import { useCallback, useMemo, useState } from "react";
import {
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Folder,
  FolderInput,
  FolderOpen,
  FileText,
  GripVertical,
  Sparkles,
  Trash2,
} from "lucide-react";
import { cn } from "../../app/components/ui/utils";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../../app/components/ui/select";

export type LibraryFile = {
  relative_path: string;
  title: string;
  kind: string;
  topic?: string | null;
  source?: string;
  read_scroll_top?: number;
  bookmark_scroll_top?: number | null;
};

export type LibraryFolderNode = {
  path: string;
  name: string;
  folders: LibraryFolderNode[];
  files: LibraryFile[];
};

export type LibraryTree = {
  root: LibraryFolderNode;
};

const KIND_BADGE: Record<string, string> = {
  lecture: "lecture",
  textbook: "textbook",
  quiz: "quiz",
  exercise: "exercise",
  note: "note",
};

const DRAG_PATH_KEY = "study-library-path";

function collectAllFiles(node: LibraryFolderNode): LibraryFile[] {
  const out = [...node.files];
  for (const child of node.folders) {
    out.push(...collectAllFiles(child));
  }
  return out;
}

function collectFolderOptions(
  node: LibraryFolderNode,
  depth = 0,
): { path: string; label: string }[] {
  const out: { path: string; label: string }[] = [];
  for (const child of node.folders) {
    out.push({
      path: child.path,
      label: `${"  ".repeat(depth)}${child.name}`,
    });
    out.push(...collectFolderOptions(child, depth + 1));
  }
  return out;
}

function folderOf(relativePath: string): string {
  const parts = relativePath.split("/");
  return parts.length <= 1 ? "" : parts.slice(0, -1).join("/");
}

function setDragPath(e: React.DragEvent, path: string) {
  e.dataTransfer.setData("text/plain", path);
  e.dataTransfer.setData(DRAG_PATH_KEY, path);
  e.dataTransfer.effectAllowed = "move";
}

function getDragPath(e: React.DragEvent): string {
  return e.dataTransfer.getData(DRAG_PATH_KEY) || e.dataTransfer.getData("text/plain");
}

function isLibraryDrag(e: React.DragEvent): boolean {
  return (
    e.dataTransfer.types.includes(DRAG_PATH_KEY) ||
    e.dataTransfer.types.includes("text/plain")
  );
}

function FileRow({
  file,
  depth,
  selectedFile,
  comparePaths,
  organizeMode,
  folderOptions,
  onSelectFile,
  onToggleCompare,
  onDeleteFile,
  onMoveFile,
  selectedFolder,
}: {
  file: LibraryFile;
  depth: number;
  selectedFile: string;
  comparePaths: string[];
  organizeMode: boolean;
  folderOptions: { path: string; label: string }[];
  onSelectFile: (path: string) => void;
  onToggleCompare: (path: string) => void;
  onDeleteFile?: (path: string) => void;
  onMoveFile?: (path: string, destFolder: string) => void;
  selectedFolder?: string;
}) {
  const inCompare = comparePaths.includes(file.relative_path);
  const isActive = selectedFile === file.relative_path;
  const hasBookmark = file.bookmark_scroll_top != null;
  const currentFolder = folderOf(file.relative_path);

  if (organizeMode) {
    return (
      <div
        draggable
        onDragStart={(e) => setDragPath(e, file.relative_path)}
        className={cn(
          "study-library-organize-file group",
          inCompare && "study-library-file-compare",
          isActive && !inCompare && "study-library-file-selected",
        )}
      >
        <GripVertical className="w-4 h-4 shrink-0 opacity-40 group-hover:opacity-80 cursor-grab" />
        <button
          type="button"
          onClick={() => onSelectFile(file.relative_path)}
          className="flex flex-1 items-start gap-2 min-w-0 text-left"
        >
          <FileText className="w-5 h-5 shrink-0 text-emerald-400/80 mt-0.5" />
          <span className="min-w-0 flex-1">
            <span className="block text-sm font-medium truncate">{file.title}</span>
            <span className="block text-[10px] text-slate-500 truncate">{file.relative_path}</span>
          </span>
        </button>
        <span className="study-library-kind-pill shrink-0">{KIND_BADGE[file.kind] ?? file.kind}</span>
        {hasBookmark && <span className="text-[9px] text-amber-400 shrink-0">bookmark</span>}
        {onMoveFile && (
          <Select
            value={currentFolder || "__root__"}
            onValueChange={(dest) => {
              const folder = dest === "__root__" ? "" : dest;
              if (folder !== currentFolder) onMoveFile(file.relative_path, folder);
            }}
          >
            <SelectTrigger className="h-7 w-[7.5rem] text-[10px] bg-black/30 border-emerald-900/50">
              <FolderInput className="w-3 h-3 mr-1 shrink-0" />
              <SelectValue placeholder="Move to…" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__root__" className="text-xs">
                Library root
              </SelectItem>
              {folderOptions.map((f) => (
                <SelectItem key={f.path} value={f.path} className="text-xs font-mono">
                  {f.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
        {onDeleteFile && (
          <button
            type="button"
            title="Delete file"
            onClick={() => {
              if (window.confirm(`Delete “${file.title}”?`)) onDeleteFile(file.relative_path);
            }}
            className="p-1.5 shrink-0 rounded hover:bg-red-500/20 text-red-400/80"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        )}
        <button
          type="button"
          title="Compare"
          onClick={() => onToggleCompare(file.relative_path)}
          className={cn(
            "p-1.5 shrink-0 rounded hover:bg-emerald-500/20",
            inCompare ? "text-emerald-400" : "text-slate-500",
          )}
        >
          <CheckCircle2 className="w-4 h-4" />
        </button>
      </div>
    );
  }

  return (
    <div
      draggable
      onDragStart={(e) => setDragPath(e, file.relative_path)}
      className={cn(
        "group flex items-center gap-0.5 rounded-md text-xs mb-0.5",
        inCompare && "study-library-file-compare",
        isActive && !inCompare && "study-library-file-selected",
        !isActive && !inCompare && "hover:bg-white/5",
      )}
      style={{ paddingLeft: `${4 + depth * 10}px` }}
    >
      <span className="p-0.5 opacity-0 group-hover:opacity-40 cursor-grab shrink-0">
        <GripVertical className="w-3 h-3" />
      </span>
      <button
        type="button"
        onClick={() => onSelectFile(file.relative_path)}
        className="flex flex-1 items-center gap-1.5 py-1.5 px-1 min-w-0 text-left"
      >
        <FileText className="w-3 h-3 shrink-0 opacity-70" />
        <span className="truncate flex-1">{file.title}</span>
        {hasBookmark && (
          <span className="text-[8px] text-amber-400/80 shrink-0" title="Bookmark saved">
            pin
          </span>
        )}
        <span className="text-[9px] uppercase opacity-50 shrink-0">
          {KIND_BADGE[file.kind] ?? file.kind.slice(0, 4)}
        </span>
      </button>
      {onMoveFile && selectedFolder !== undefined && folderOf(file.relative_path) !== selectedFolder && (
        <button
          type="button"
          title={`Move to ${selectedFolder || "library root"}`}
          onClick={() => onMoveFile(file.relative_path, selectedFolder)}
          className="p-1 shrink-0 rounded opacity-0 group-hover:opacity-100 hover:bg-emerald-500/20 text-emerald-300/70"
        >
          <FolderInput className="w-3 h-3" />
        </button>
      )}
      {onDeleteFile && (
        <button
          type="button"
          title="Delete file"
          onClick={() => {
            if (window.confirm(`Delete “${file.title}”?`)) onDeleteFile(file.relative_path);
          }}
          className="p-1 shrink-0 rounded opacity-0 group-hover:opacity-100 hover:bg-red-500/20 text-red-400/80"
        >
          <Trash2 className="w-3 h-3" />
        </button>
      )}
      <button
        type="button"
        title="Compare"
        onClick={() => onToggleCompare(file.relative_path)}
        className={cn(
          "p-1 shrink-0 rounded hover:bg-emerald-500/20",
          inCompare ? "text-emerald-400" : "text-slate-500",
        )}
      >
        <CheckCircle2 className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}

function FolderBranch({
  node,
  depth,
  expanded,
  selectedFolder,
  selectedFile,
  comparePaths,
  organizeMode,
  folderOptions,
  dragOverFolder,
  onSelectFolder,
  onSelectFile,
  onToggleCompare,
  onToggleExpand,
  onMoveFile,
  onDeleteFolder,
  onSummarizeFolder,
  onDeleteFile,
  onDragFolderHover,
  onEnsureExpanded,
  summarizingFolder,
}: {
  node: LibraryFolderNode;
  depth: number;
  expanded: Set<string>;
  selectedFolder: string;
  selectedFile: string;
  comparePaths: string[];
  organizeMode: boolean;
  folderOptions: { path: string; label: string }[];
  dragOverFolder: string | null;
  onSelectFolder: (path: string) => void;
  onSelectFile: (path: string) => void;
  onToggleCompare: (path: string) => void;
  onToggleExpand: (path: string) => void;
  onMoveFile?: (path: string, destFolder: string) => void;
  onDeleteFolder?: (path: string) => void;
  onSummarizeFolder?: (path: string) => void;
  onDeleteFile?: (path: string) => void;
  onDragFolderHover?: (path: string | null) => void;
  onEnsureExpanded?: (path: string) => void;
  summarizingFolder?: string;
}) {
  const isSelected = selectedFolder === node.path;
  const isOpen = expanded.has(node.path);
  const dropActive = dragOverFolder === node.path;
  const fileCount = node.files.length + node.folders.reduce((n, c) => n + c.files.length, 0);

  const handleDragOver = (e: React.DragEvent) => {
    if (!isLibraryDrag(e)) return;
    e.preventDefault();
    e.stopPropagation();
    e.dataTransfer.dropEffect = "move";
    onDragFolderHover?.(node.path);
    if (!isOpen) onEnsureExpanded?.(node.path);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    onDragFolderHover?.(null);
    const path = getDragPath(e);
    if (!path || !onMoveFile) return;
    if (folderOf(path) === node.path) return;
    onMoveFile(path, node.path);
  };

  if (node.path === "") return null;

  if (organizeMode) {
    return (
      <div className="space-y-1">
        <div
          className={cn("study-library-organize-folder", dropActive && "study-library-drop-active")}
          onDragOver={handleDragOver}
          onDragLeave={() => onDragFolderHover?.(null)}
          onDrop={handleDrop}
        >
          <button
            type="button"
            onClick={() => {
              onSelectFolder(node.path);
              onToggleExpand(node.path);
            }}
            className="flex flex-1 items-center gap-2 min-w-0 text-left"
          >
            {isOpen ? (
              <ChevronDown className="w-4 h-4 shrink-0 text-emerald-400/70" />
            ) : (
              <ChevronRight className="w-4 h-4 shrink-0 text-emerald-400/70" />
            )}
            {isSelected ? (
              <FolderOpen className="w-6 h-6 shrink-0 text-emerald-400" />
            ) : (
              <Folder className="w-6 h-6 shrink-0 text-emerald-300/80" />
            )}
            <span className="min-w-0 flex-1">
              <span className="block text-sm font-semibold text-emerald-100 truncate">{node.name}</span>
              <span className="block text-[10px] text-slate-500 truncate">
                {node.path} · {node.files.length} file{node.files.length !== 1 ? "s" : ""}
              </span>
            </span>
          </button>
          {onSummarizeFolder && (
            <button
              type="button"
              title="Summarize folder"
              disabled={summarizingFolder === node.path}
              onClick={() => onSummarizeFolder(node.path)}
              className="p-2 rounded-lg hover:bg-emerald-500/20 text-emerald-300/80"
            >
              <Sparkles className={cn("w-4 h-4", summarizingFolder === node.path && "animate-pulse")} />
            </button>
          )}
          {onDeleteFolder && (
            <button
              type="button"
              title="Delete folder"
              onClick={() => {
                if (
                  window.confirm(
                    `Delete folder “${node.name}” and all notes inside? This cannot be undone.`,
                  )
                ) {
                  onDeleteFolder(node.path);
                }
              }}
              className="p-2 rounded-lg hover:bg-red-500/20 text-red-400/80"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          )}
        </div>
        {dropActive && (
          <p className="text-[10px] text-emerald-300 px-2">Drop here to move into {node.name}</p>
        )}
        {isOpen && (
          <div className="pl-3 space-y-1 border-l border-emerald-900/40 ml-3">
            {node.files.map((f) => (
              <FileRow
                key={f.relative_path}
                file={f}
                depth={depth + 1}
                selectedFile={selectedFile}
                comparePaths={comparePaths}
                organizeMode={organizeMode}
                folderOptions={folderOptions}
                onSelectFile={onSelectFile}
                onToggleCompare={onToggleCompare}
                onDeleteFile={onDeleteFile}
                onMoveFile={onMoveFile}
                selectedFolder={selectedFolder}
              />
            ))}
            {node.folders.map((child) => (
              <FolderBranch
                key={child.path}
                node={child}
                depth={depth + 1}
                expanded={expanded}
                selectedFolder={selectedFolder}
                selectedFile={selectedFile}
                comparePaths={comparePaths}
                organizeMode={organizeMode}
                folderOptions={folderOptions}
                dragOverFolder={dragOverFolder}
                onSelectFolder={onSelectFolder}
                onSelectFile={onSelectFile}
                onToggleCompare={onToggleCompare}
                onToggleExpand={onToggleExpand}
                onMoveFile={onMoveFile}
                onDeleteFolder={onDeleteFolder}
                onSummarizeFolder={onSummarizeFolder}
                onDeleteFile={onDeleteFile}
                onDragFolderHover={onDragFolderHover}
                onEnsureExpanded={onEnsureExpanded}
                summarizingFolder={summarizingFolder}
              />
            ))}
            {node.files.length === 0 && node.folders.length === 0 && (
              <p className="text-[10px] text-slate-500 py-2 px-1">Empty — drag notes here</p>
            )}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="select-none">
      <div
        className={cn(
          "group flex items-center gap-0.5 rounded-md",
          dropActive && "ring-1 ring-emerald-400/60 bg-emerald-900/20",
        )}
        style={{ paddingLeft: `${4 + depth * 10}px` }}
        onDragOver={handleDragOver}
        onDragLeave={() => onDragFolderHover?.(null)}
        onDrop={handleDrop}
      >
        <button
          type="button"
          onClick={() => {
            onSelectFolder(node.path);
            onToggleExpand(node.path);
          }}
          className={cn(
            "flex flex-1 items-center gap-1 text-left text-xs rounded-md px-1 py-1 truncate min-w-0",
            isSelected ? "text-emerald-300 font-medium" : "text-slate-300 hover:text-emerald-200",
          )}
        >
          {isOpen ? (
            <ChevronDown className="w-3 h-3 shrink-0 opacity-60" />
          ) : (
            <ChevronRight className="w-3 h-3 shrink-0 opacity-60" />
          )}
          {isSelected ? (
            <FolderOpen className="w-3 h-3 shrink-0 text-emerald-400" />
          ) : (
            <Folder className="w-3 h-3 shrink-0" />
          )}
          <span className="truncate">{node.name}</span>
          {fileCount > 0 && (
            <span className="text-[9px] opacity-50 shrink-0">({fileCount})</span>
          )}
        </button>
        {onSummarizeFolder && (
          <button
            type="button"
            title="Summarize folder"
            disabled={summarizingFolder === node.path}
            onClick={() => onSummarizeFolder(node.path)}
            className="p-1 shrink-0 rounded opacity-0 group-hover:opacity-100 hover:bg-emerald-500/20 text-emerald-300/80"
          >
            <Sparkles className={cn("w-3 h-3", summarizingFolder === node.path && "animate-pulse")} />
          </button>
        )}
        {onDeleteFolder && (
          <button
            type="button"
            title="Delete folder"
            onClick={() => {
              if (
                window.confirm(`Delete folder “${node.name}” and all notes inside? This cannot be undone.`)
              ) {
                onDeleteFolder(node.path);
              }
            }}
            className="p-1 shrink-0 rounded opacity-0 group-hover:opacity-100 hover:bg-red-500/20 text-red-400/80"
          >
            <Trash2 className="w-3 h-3" />
          </button>
        )}
      </div>
      {isOpen &&
        node.files.map((f) => (
          <FileRow
            key={f.relative_path}
            file={f}
            depth={depth + 1}
            selectedFile={selectedFile}
            comparePaths={comparePaths}
            organizeMode={organizeMode}
            folderOptions={folderOptions}
            onSelectFile={onSelectFile}
            onToggleCompare={onToggleCompare}
            onDeleteFile={onDeleteFile}
            onMoveFile={onMoveFile}
            selectedFolder={selectedFolder}
          />
        ))}
      {isOpen &&
        node.folders.map((child) => (
          <FolderBranch
            key={child.path}
            node={child}
            depth={depth + 1}
            expanded={expanded}
            selectedFolder={selectedFolder}
            selectedFile={selectedFile}
            comparePaths={comparePaths}
            organizeMode={organizeMode}
            folderOptions={folderOptions}
            dragOverFolder={dragOverFolder}
            onSelectFolder={onSelectFolder}
            onSelectFile={onSelectFile}
            onToggleCompare={onToggleCompare}
            onToggleExpand={onToggleExpand}
            onMoveFile={onMoveFile}
            onDeleteFolder={onDeleteFolder}
            onSummarizeFolder={onSummarizeFolder}
            onDeleteFile={onDeleteFile}
            onDragFolderHover={onDragFolderHover}
            onEnsureExpanded={onEnsureExpanded}
            summarizingFolder={summarizingFolder}
          />
        ))}
    </div>
  );
}

type Props = {
  tree: LibraryTree | null;
  selectedFolder: string;
  selectedFile: string;
  comparePaths: string[];
  organizeMode?: boolean;
  onOrganizeModeChange?: (value: boolean) => void;
  onSelectFolder: (path: string) => void;
  onSelectFile: (relativePath: string) => void;
  onToggleCompare: (relativePath: string) => void;
  onMoveFile?: (path: string, destFolder: string) => void;
  onDeleteFile?: (path: string) => void;
  onDeleteFolder?: (path: string) => void;
  onSummarizeFolder?: (path: string) => void;
  summarizingFolder?: string;
};

export function StudyLibraryTree({
  tree,
  selectedFolder,
  selectedFile,
  comparePaths,
  organizeMode = false,
  onOrganizeModeChange,
  onSelectFolder,
  onSelectFile,
  onToggleCompare,
  onMoveFile,
  onDeleteFile,
  onDeleteFolder,
  onSummarizeFolder,
  summarizingFolder,
}: Props) {
  const defaultExpanded = useMemo(
    () => new Set(["", ...(tree?.root.folders.map((f) => f.path) ?? [])]),
    [tree],
  );
  const [expanded, setExpanded] = useState<Set<string>>(defaultExpanded);
  const [dragOverFolder, setDragOverFolder] = useState<string | null>(null);
  const [rootDropHover, setRootDropHover] = useState(false);

  const handleToggleExpand = useCallback((path: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  }, []);

  const ensureExpanded = useCallback((path: string) => {
    setExpanded((prev) => {
      if (prev.has(path)) return prev;
      const next = new Set(prev);
      next.add(path);
      return next;
    });
  }, []);

  const folderOptions = useMemo(
    () => (tree ? collectFolderOptions(tree.root) : []),
    [tree],
  );

  if (!tree) return null;
  const allFiles = collectAllFiles(tree.root);
  const rootFiles = tree.root.files;

  const handleRootDragOver = (e: React.DragEvent) => {
    if (!isLibraryDrag(e)) return;
    e.preventDefault();
    setRootDropHover(true);
    setDragOverFolder(null);
  };

  const handleRootDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setRootDropHover(false);
    const path = getDragPath(e);
    if (!path || !onMoveFile) return;
    if (folderOf(path) === "") return;
    onMoveFile(path, "");
  };

  return (
    <div className={cn("space-y-1", organizeMode && "study-library-organize-panel")}>
      <div className="flex items-center justify-between gap-2 px-1 pb-1 border-b border-emerald-900/30">
        {onOrganizeModeChange && (
          <button
            type="button"
            onClick={() => onOrganizeModeChange(!organizeMode)}
            className={cn(
              "text-[10px] px-2 py-1 rounded-md border transition-colors",
              organizeMode
                ? "bg-emerald-900/40 border-emerald-500/50 text-emerald-200"
                : "border-emerald-900/40 text-slate-400 hover:text-emerald-200",
            )}
          >
            {organizeMode ? "Organize mode on" : "Organize files"}
          </button>
        )}
        <span className="text-[9px] text-slate-500 ml-auto">
          {organizeMode ? "Drag or use Move to…" : "Drag onto folders"}
        </span>
      </div>

      <div
        className={cn(
          "rounded-md",
          rootDropHover && "study-library-drop-active",
          organizeMode && "study-library-organize-folder mb-2",
        )}
        onDragOver={handleRootDragOver}
        onDragLeave={() => setRootDropHover(false)}
        onDrop={handleRootDrop}
      >
        <button
          type="button"
          onClick={() => onSelectFolder("")}
          className={cn(
            "w-full flex items-center gap-2 text-left rounded-md px-2 py-1.5 font-medium",
            organizeMode ? "text-sm" : "text-xs",
            selectedFolder === "" ? "text-emerald-300 bg-emerald-900/20" : "text-slate-300 hover:bg-white/5",
          )}
        >
          <Folder className={organizeMode ? "w-5 h-5" : "w-3.5 h-3.5"} />
          All notes{allFiles.length > 0 ? ` (${allFiles.length})` : ""}
        </button>
      </div>

      {rootFiles.length > 0 && (
        <div className="space-y-1">
          <p className="text-[10px] uppercase tracking-wide text-slate-500 px-1 pt-1">
            Unfiled ({rootFiles.length})
          </p>
          {rootFiles.map((f) => (
            <FileRow
              key={f.relative_path}
              file={f}
              depth={0}
              selectedFile={selectedFile}
              comparePaths={comparePaths}
              organizeMode={organizeMode}
              folderOptions={folderOptions}
              onSelectFile={onSelectFile}
              onToggleCompare={onToggleCompare}
              onDeleteFile={onDeleteFile}
              onMoveFile={onMoveFile}
              selectedFolder={selectedFolder}
            />
          ))}
        </div>
      )}

      {tree.root.folders.length > 0 && (
        <p className="text-[10px] uppercase tracking-wide text-slate-500 px-1 pt-2">Folders</p>
      )}

      {tree.root.folders.map((f) => (
        <FolderBranch
          key={f.path}
          node={f}
          depth={0}
          expanded={expanded}
          selectedFolder={selectedFolder}
          selectedFile={selectedFile}
          comparePaths={comparePaths}
          organizeMode={organizeMode}
          folderOptions={folderOptions}
          dragOverFolder={dragOverFolder}
          onSelectFolder={onSelectFolder}
          onSelectFile={onSelectFile}
          onToggleCompare={onToggleCompare}
          onToggleExpand={handleToggleExpand}
          onEnsureExpanded={ensureExpanded}
          onMoveFile={onMoveFile}
          onDeleteFolder={onDeleteFolder}
          onSummarizeFolder={onSummarizeFolder}
          onDeleteFile={onDeleteFile}
          onDragFolderHover={setDragOverFolder}
          summarizingFolder={summarizingFolder}
        />
      ))}

      {allFiles.length === 0 && tree.root.folders.length === 0 && (
        <p className="text-[10px] text-slate-500 px-2 py-2">No notes yet — generate from captions.</p>
      )}

      {comparePaths.length > 0 && (
        <p className="text-[10px] text-center text-emerald-300/80 pt-2 border-t border-emerald-900/30 mt-2">
          Comparing: {comparePaths.length} file{comparePaths.length !== 1 ? "s" : ""} selected
        </p>
      )}
    </div>
  );
}

export function findLibraryFile(tree: LibraryTree | null, path: string): LibraryFile | undefined {
  if (!tree) return undefined;
  return collectAllFiles(tree.root).find((f) => f.relative_path === path);
}

export function listLibraryFolders(tree: LibraryTree | null): { path: string; label: string }[] {
  if (!tree) return [];
  return collectFolderOptions(tree.root);
}
