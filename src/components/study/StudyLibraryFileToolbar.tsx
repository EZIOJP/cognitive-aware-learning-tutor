import { useRef } from "react";
import {
  ArrowDownAZ,
  Columns2,
  FilePlus,
  FolderPlus,
  LayoutGrid,
  List,
  MoreHorizontal,
  Pencil,
  Sparkles,
  Trash2,
  Upload,
} from "lucide-react";
import { Button } from "../../app/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "../../app/components/ui/dropdown-menu";
import { cn } from "../../app/components/ui/utils";
import type { LibraryExplorerSelection, LibrarySortMode } from "./studyLibraryUtils";
import { isImportableNoteFile } from "./studyLibraryUtils";

type Props = {
  selection: LibraryExplorerSelection;
  comparePaths: string[];
  viewMode: "grid" | "list";
  sortMode: LibrarySortMode;
  importing?: boolean;
  folderSummarizeDisabled?: boolean;
  onNewFile: () => void;
  onImportFiles: (files: File[]) => void;
  onRename: () => void;
  onToggleCompare: () => void;
  onDelete: () => void;
  onNewFolder: () => void;
  onSummarizeFolder: () => void;
  onSortToggle: () => void;
  onViewModeChange: (mode: "grid" | "list") => void;
};

export function StudyLibraryFileToolbar({
  selection,
  comparePaths,
  viewMode,
  sortMode,
  importing,
  folderSummarizeDisabled,
  onNewFile,
  onImportFiles,
  onRename,
  onToggleCompare,
  onDelete,
  onNewFolder,
  onSummarizeFolder,
  onSortToggle,
  onViewModeChange,
}: Props) {
  const importRef = useRef<HTMLInputElement>(null);
  const fileSelected = selection?.kind === "file";
  const folderSelected = selection?.kind === "folder";
  const inCompare =
    fileSelected && selection ? comparePaths.includes(selection.path) : false;

  const handleImportPick = (fileList: FileList | null) => {
    if (!fileList?.length) return;
    const picked = Array.from(fileList).filter(isImportableNoteFile);
    if (!picked.length) {
      window.alert("Choose .md, .markdown, or .txt files.");
      return;
    }
    onImportFiles(picked);
    if (importRef.current) importRef.current.value = "";
  };

  return (
    <div className="study-library-file-toolbar shrink-0">
      <Button type="button" size="sm" variant="default" className="h-8 text-xs gap-1" onClick={onNewFile}>
        <FilePlus className="w-3.5 h-3.5" />
        New
      </Button>
      <Button
        type="button"
        size="sm"
        variant="outline"
        className="h-8 text-xs gap-1"
        disabled={importing}
        onClick={() => importRef.current?.click()}
      >
        <Upload className="w-3.5 h-3.5" />
        Import
      </Button>
      <input
        ref={importRef}
        type="file"
        accept=".md,.markdown,.txt"
        multiple
        className="sr-only"
        onChange={(e) => handleImportPick(e.target.files)}
      />

      <div className="study-library-file-toolbar-divider" aria-hidden />

      <Button
        type="button"
        size="icon"
        variant="outline"
        className="h-8 w-8"
        disabled={!fileSelected}
        onClick={onRename}
        title="Rename note"
        aria-label="Rename note"
      >
        <Pencil className="w-3.5 h-3.5" />
      </Button>
      <Button
        type="button"
        size="icon"
        variant={inCompare ? "secondary" : "outline"}
        className="h-8 w-8"
        disabled={!fileSelected}
        onClick={onToggleCompare}
        title="Compare"
        aria-label="Compare"
      >
        <Columns2 className="w-3.5 h-3.5" />
      </Button>
      <Button
        type="button"
        size="icon"
        variant="outline"
        className="h-8 w-8 text-destructive hover:text-destructive"
        disabled={!selection}
        onClick={onDelete}
        title="Delete"
        aria-label="Delete"
      >
        <Trash2 className="w-3.5 h-3.5" />
      </Button>

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button type="button" size="icon" variant="ghost" className="h-8 w-8" title="More">
            <MoreHorizontal className="w-4 h-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" className="min-w-[10rem]">
          <DropdownMenuItem onClick={onNewFolder}>
            <FolderPlus className="w-4 h-4 mr-2" />
            New folder
          </DropdownMenuItem>
          {folderSelected ? (
            <DropdownMenuItem disabled={folderSummarizeDisabled} onClick={onSummarizeFolder}>
              <Sparkles className="w-4 h-4 mr-2" />
              Summarize folder
            </DropdownMenuItem>
          ) : null}
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={onSortToggle}>
            <ArrowDownAZ className="w-4 h-4 mr-2" />
            Sort {sortMode === "name-asc" ? "Z → A" : "A → Z"}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <div className="study-library-file-toolbar-divider hidden sm:block" aria-hidden />

      <div className="study-library-file-toolbar-views hidden sm:flex">
        <button
          type="button"
          className={cn("study-library-explorer-tool-icon", viewMode === "list" && "active")}
          onClick={() => onViewModeChange("list")}
          title="List view"
          aria-label="List view"
        >
          <List className="w-4 h-4" />
        </button>
        <button
          type="button"
          className={cn("study-library-explorer-tool-icon", viewMode === "grid" && "active")}
          onClick={() => onViewModeChange("grid")}
          title="Grid view"
          aria-label="Grid view"
        >
          <LayoutGrid className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}
