import { useEffect, useMemo, useRef } from "react";
import { FileText, FolderOpen, Loader2, Search, X } from "lucide-react";
import type { LibrarySearchHit, LibraryTree } from "../../api/transcriptsClient";
import { StudyLibraryExplorer } from "./StudyLibraryExplorer";
import { Button } from "../../app/components/ui/button";
import { cn } from "../../app/components/ui/utils";

const MATCH_KIND_LABEL: Record<LibrarySearchHit["match_kind"], string> = {
  topic: "Topic",
  function: "Function",
  text: "In section",
  file: "File",
};

function hitKey(hit: LibrarySearchHit, index: number) {
  return `${hit.relative_path}:${hit.topic_id ?? ""}:${hit.match_kind}:${hit.label ?? hit.snippet}:${index}`;
}

type FileSearchGroup = {
  relative_path: string;
  title: string;
  body_match_count: number;
  section_hit_count: number;
  hits: LibrarySearchHit[];
};

function groupSearchByFile(results: LibrarySearchHit[]): FileSearchGroup[] {
  const order: string[] = [];
  const groups = new Map<string, FileSearchGroup>();

  for (const hit of results) {
    let group = groups.get(hit.relative_path);
    if (!group) {
      group = {
        relative_path: hit.relative_path,
        title: hit.title,
        body_match_count: hit.body_match_count ?? 0,
        section_hit_count: hit.section_hit_count ?? 0,
        hits: [],
      };
      groups.set(hit.relative_path, group);
      order.push(hit.relative_path);
    }
    group.hits.push(hit);
  }

  return order.map((path) => groups.get(path)!);
}

type Props = {
  tree: LibraryTree;
  browsePath: string;
  selectedFile: string;
  searchQuery: string;
  onSearchQueryChange: (q: string) => void;
  searchResults: LibrarySearchHit[];
  searchLoading: boolean;
  searchError?: string | null;
  onBrowsePath: (path: string) => void;
  onOpenNote: (path: string) => void;
  onClose: () => void;
  comparePaths?: string[];
  onToggleCompare?: (path: string) => void;
  onMoveFile?: (path: string, destFolder: string) => void;
  onImportFiles?: (files: File[], destFolder: string) => void;
  onDeleteFile?: (path: string) => void;
  onDeleteFolder?: (path: string) => void;
  onSummarizeFolder?: (path: string) => void;
  onNewFolder?: () => void;
  onNewFile?: () => void;
  viewMode: "grid" | "list";
  onViewModeChange: (mode: "grid" | "list") => void;
  summarizingFolder?: string;
  importing?: boolean;
};

export function StudyLibraryBrowsePanel({
  tree,
  browsePath,
  selectedFile,
  searchQuery,
  onSearchQueryChange,
  searchResults,
  searchLoading,
  searchError = null,
  onBrowsePath,
  onOpenNote,
  onClose,
  comparePaths = [],
  onToggleCompare,
  onMoveFile,
  onImportFiles,
  onDeleteFile,
  onDeleteFolder,
  onSummarizeFolder,
  onNewFolder,
  onNewFile,
  viewMode,
  onViewModeChange,
  summarizingFolder,
  importing,
}: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const showSearchResults = searchQuery.trim().length > 0;
  const searchGroups = useMemo(() => groupSearchByFile(searchResults), [searchResults]);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        inputRef.current?.focus();
        inputRef.current?.select();
      }
      if (e.key === "Escape" && document.activeElement === inputRef.current && searchQuery) {
        e.preventDefault();
        onSearchQueryChange("");
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onSearchQueryChange, searchQuery]);

  return (
    <section className="study-library-browse flex flex-col flex-1 min-h-0 overflow-hidden">
      <div className="study-library-browse-search shrink-0">
        <Search className="w-5 h-5 shrink-0 text-muted-foreground" aria-hidden />
        <input
          ref={inputRef}
          type="text"
          value={searchQuery}
          onChange={(e) => onSearchQueryChange(e.target.value)}
          placeholder="Search topics, functions (merge, value_counts)…"
          className="study-library-browse-search-input"
          aria-label="Search notes"
          autoComplete="off"
          spellCheck={false}
        />
        {searchLoading ? (
          <Loader2 className="w-4 h-4 shrink-0 animate-spin text-muted-foreground" />
        ) : searchQuery ? (
          <button
            type="button"
            className="study-library-browse-search-clear"
            onClick={() => onSearchQueryChange("")}
            aria-label="Clear search"
          >
            <X className="w-4 h-4" />
          </button>
        ) : (
          <kbd className="study-library-browse-search-kbd hidden sm:inline">Ctrl+K</kbd>
        )}
        <Button type="button" variant="outline" size="sm" className="h-8 shrink-0" onClick={onClose}>
          Done
        </Button>
      </div>

      <div className="flex flex-1 min-h-0 overflow-hidden">
        {showSearchResults ? (
          <div className="study-library-browse-results flex-1 min-h-0 overflow-y-auto study-library-markdown-scroll">
            {searchLoading && searchResults.length === 0 ? (
              <div className="flex items-center justify-center py-16 text-muted-foreground text-sm gap-2">
                <Loader2 className="w-4 h-4 animate-spin" />
                Searching…
              </div>
            ) : searchError ? (
              <div className="study-library-explorer-empty">
                <Search className="w-10 h-10 text-destructive/50 mb-3" />
                <p className="text-sm font-medium">Search unavailable</p>
                <p className="text-xs text-muted-foreground mt-1 max-w-sm text-center">{searchError}</p>
              </div>
            ) : searchResults.length === 0 ? (
              <div className="study-library-explorer-empty">
                <Search className="w-10 h-10 text-muted-foreground/40 mb-3" />
                <p className="text-sm font-medium">No matches</p>
                <p className="text-xs text-muted-foreground mt-1">Try different keywords from your notes.</p>
              </div>
            ) : (
              <ul className="study-library-browse-results-list">
                {searchGroups.map((group) => (
                  <li key={group.relative_path} className="study-library-browse-file-group">
                    <div className="study-library-browse-file-header">
                      <FileText className="w-4 h-4 shrink-0 text-primary/80" />
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-semibold truncate">{group.title}</p>
                        <p className="text-[11px] text-muted-foreground truncate">
                          {group.relative_path.split("/").pop()}
                        </p>
                      </div>
                      <span className="study-library-browse-match-badge shrink-0">
                        {group.body_match_count}× in file
                      </span>
                    </div>
                    <ul className="study-library-browse-file-hits">
                      {group.hits.map((hit, index) => (
                        <li key={hitKey(hit, index)}>
                          <button
                            type="button"
                            className={cn(
                              "study-library-browse-result study-library-browse-result--nested",
                              selectedFile === hit.relative_path && "study-library-browse-result--active",
                            )}
                            onClick={() => onOpenNote(hit.relative_path)}
                          >
                            <div className="min-w-0 flex-1 text-left pl-1">
                              <div className="flex flex-wrap items-center gap-1.5 min-w-0">
                                <span
                                  className={cn(
                                    "study-library-browse-match-kind",
                                    hit.match_kind === "function" && "study-library-browse-match-kind--fn",
                                    hit.match_kind === "topic" && "study-library-browse-match-kind--topic",
                                  )}
                                >
                                  {MATCH_KIND_LABEL[hit.match_kind]}
                                </span>
                                {hit.topic_id ? (
                                  <code className="text-[11px] text-primary font-medium shrink-0">
                                    {hit.topic_id}
                                  </code>
                                ) : null}
                                <span className="font-medium text-sm truncate min-w-0">
                                  {hit.label || hit.topic_title || hit.title}
                                </span>
                              </div>
                              {hit.snippet && hit.snippet !== hit.label ? (
                                <p className="text-xs text-foreground/75 mt-1 line-clamp-2 leading-relaxed font-mono">
                                  {hit.snippet}
                                </p>
                              ) : hit.match_kind === "function" && hit.snippet ? (
                                <p className="text-xs text-muted-foreground mt-1 line-clamp-2">{hit.snippet}</p>
                              ) : null}
                            </div>
                          </button>
                        </li>
                      ))}
                    </ul>
                  </li>
                ))}
              </ul>
            )}
          </div>
        ) : (
          <div className="flex flex-1 min-h-0">
            <aside className="study-library-browse-hint shrink-0 hidden lg:flex flex-col justify-center px-4 border-r border-border max-w-[12rem]">
              <FolderOpen className="w-8 h-8 text-amber-400/90 mb-2" />
              <p className="text-xs text-muted-foreground leading-relaxed">
                Browse folders or type to search across every note — like Paperless.
              </p>
            </aside>
            <div className="flex-1 min-h-0 flex flex-col">
              <StudyLibraryExplorer
                tree={tree}
                browsePath={browsePath}
                selectedFile={selectedFile}
                comparePaths={comparePaths}
                onBrowsePath={onBrowsePath}
                onSelectFile={onOpenNote}
                onToggleCompare={onToggleCompare}
                onMoveFile={onMoveFile}
                onImportFiles={onImportFiles}
                onDeleteFile={onDeleteFile}
                onDeleteFolder={onDeleteFolder}
                onSummarizeFolder={onSummarizeFolder}
                onNewFolder={onNewFolder}
                onNewFile={onNewFile}
                viewMode={viewMode}
                onViewModeChange={onViewModeChange}
                summarizingFolder={summarizingFolder}
                importing={importing}
              />
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
