import { useEffect, useRef } from "react";
import {
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  FileText,
  Loader2,
  Search,
  X,
} from "lucide-react";
import type { LibrarySearchHit } from "../../api/transcriptsClient";
import type { InNoteMatch } from "./inNoteSearch";
import { Button } from "../../app/components/ui/button";
import { cn } from "../../app/components/ui/utils";

export type SearchScope = "current" | "library";
export type LibrarySearchFilter = "all" | "topics" | "functions" | "text";

type Props = {
  scope: SearchScope;
  onScopeChange: (scope: SearchScope) => void;
  filter: LibrarySearchFilter;
  onFilterChange: (filter: LibrarySearchFilter) => void;
  query: string;
  onQueryChange: (q: string) => void;
  currentNoteOpen: boolean;
  currentNoteTitle?: string;
  inNoteMatches: InNoteMatch[];
  inNoteMatchIndex: number;
  onInNotePrev: () => void;
  onInNoteNext: () => void;
  onJumpToInNoteMatch: (match: InNoteMatch) => void;
  libraryResults: LibrarySearchHit[];
  libraryLoading: boolean;
  libraryError?: string | null;
  onOpenLibraryHit: (path: string) => void;
  inputRef?: React.RefObject<HTMLInputElement | null>;
  compact?: boolean;
};

const SCOPE_LABEL: Record<SearchScope, string> = {
  current: "This note",
  library: "All notes",
};

const FILTER_LABEL: Record<LibrarySearchFilter, string> = {
  all: "Everything",
  topics: "Topics",
  functions: "Functions",
  text: "Body text",
};

function groupLibraryHits(results: LibrarySearchHit[]) {
  const order: string[] = [];
  const map = new Map<string, LibrarySearchHit[]>();
  for (const hit of results) {
    if (!map.has(hit.relative_path)) {
      map.set(hit.relative_path, []);
      order.push(hit.relative_path);
    }
    map.get(hit.relative_path)!.push(hit);
  }
  return order.map((path) => ({
    path,
    title: map.get(path)![0]!.title,
    count: map.get(path)![0]!.body_match_count ?? 0,
    hits: map.get(path)!,
  }));
}

export function StudyLibrarySearchBar({
  scope,
  onScopeChange,
  filter,
  onFilterChange,
  query,
  onQueryChange,
  currentNoteOpen,
  currentNoteTitle,
  inNoteMatches,
  inNoteMatchIndex,
  onInNotePrev,
  onInNoteNext,
  onJumpToInNoteMatch,
  libraryResults,
  libraryLoading,
  libraryError = null,
  onOpenLibraryHit,
  inputRef: externalInputRef,
  compact = false,
}: Props) {
  const localRef = useRef<HTMLInputElement>(null);
  const inputRef = externalInputRef ?? localRef;
  const showPanel = query.trim().length > 0;
  const libraryGroups = groupLibraryHits(libraryResults);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        inputRef.current?.focus();
        inputRef.current?.select();
      }
      if (e.key === "Escape" && document.activeElement === inputRef.current) {
        onQueryChange("");
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [inputRef, onQueryChange]);

  return (
    <div className={cn("study-library-search-bar-wrap relative min-w-0", compact && "flex-1")}>
      <div className="study-library-search-bar">
        <Search className="w-4 h-4 shrink-0 text-primary" aria-hidden />

        <select
          value={scope}
          onChange={(e) => onScopeChange(e.target.value as SearchScope)}
          className="study-library-search-scope"
          aria-label="Search scope"
          title="Search scope"
        >
          <option value="current" disabled={!currentNoteOpen}>
            {SCOPE_LABEL.current}
          </option>
          <option value="library">{SCOPE_LABEL.library}</option>
        </select>

        {scope === "library" ? (
          <select
            value={filter}
            onChange={(e) => onFilterChange(e.target.value as LibrarySearchFilter)}
            className="study-library-search-filter"
            aria-label="Search filter"
            title="What to search"
          >
            {(Object.keys(FILTER_LABEL) as LibrarySearchFilter[]).map((k) => (
              <option key={k} value={k}>
                {FILTER_LABEL[k]}
              </option>
            ))}
          </select>
        ) : null}

        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => onQueryChange(e.target.value)}
          placeholder={
            scope === "current"
              ? currentNoteOpen
                ? `Search in “${currentNoteTitle ?? "this note"}”…`
                : "Open a note to search inside it"
              : "Search all notes — topics, functions, body…"
          }
          disabled={scope === "current" && !currentNoteOpen}
          className="study-library-search-input"
          aria-label="Search"
          autoComplete="off"
          spellCheck={false}
        />

        {scope === "current" && inNoteMatches.length > 0 ? (
          <div className="flex items-center gap-0.5 shrink-0">
            <span className="text-[10px] tabular-nums text-muted-foreground px-1">
              {inNoteMatchIndex + 1}/{inNoteMatches.length}
            </span>
            <Button type="button" variant="ghost" size="icon" className="h-7 w-7" onClick={onInNotePrev}>
              <ChevronLeft className="w-4 h-4" />
            </Button>
            <Button type="button" variant="ghost" size="icon" className="h-7 w-7" onClick={onInNoteNext}>
              <ChevronRight className="w-4 h-4" />
            </Button>
          </div>
        ) : null}

        {libraryLoading ? (
          <Loader2 className="w-4 h-4 shrink-0 animate-spin text-muted-foreground" />
        ) : query ? (
          <button
            type="button"
            className="study-library-browse-search-clear"
            onClick={() => onQueryChange("")}
            aria-label="Clear search"
          >
            <X className="w-4 h-4" />
          </button>
        ) : (
          <kbd className="study-library-browse-search-kbd hidden xl:inline">Ctrl+K</kbd>
        )}
      </div>

      {showPanel ? (
        <div className="study-library-search-dropdown study-library-markdown-scroll">
          {scope === "current" ? (
            inNoteMatches.length === 0 ? (
              <p className="text-xs text-muted-foreground px-3 py-4 text-center">
                No matches in this note.
              </p>
            ) : (
              <ul className="study-library-search-dropdown-list">
                {inNoteMatches.map((m, i) => (
                  <li key={`${m.line}-${m.charOffset}`}>
                    <button
                      type="button"
                      className={cn(
                        "study-library-search-dropdown-item",
                        i === inNoteMatchIndex && "study-library-search-dropdown-item--active",
                      )}
                      onClick={() => onJumpToInNoteMatch(m)}
                    >
                      <span className="text-[10px] text-muted-foreground shrink-0">L{m.line}</span>
                      <span className="text-xs font-mono truncate">{m.snippet}</span>
                    </button>
                  </li>
                ))}
              </ul>
            )
          ) : libraryLoading && libraryResults.length === 0 ? (
            <p className="text-xs text-muted-foreground px-3 py-4 text-center flex items-center justify-center gap-2">
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              Searching library…
            </p>
          ) : libraryError ? (
            <p className="text-xs text-destructive px-3 py-4 text-center">{libraryError}</p>
          ) : libraryGroups.length === 0 ? (
            <p className="text-xs text-muted-foreground px-3 py-4 text-center">No library matches.</p>
          ) : (
            <ul className="study-library-search-dropdown-list">
              {libraryGroups.map((group) => (
                <li key={group.path} className="study-library-search-file-block">
                  <div className="study-library-search-file-head">
                    <FileText className="w-3.5 h-3.5 shrink-0 text-primary/80" />
                    <span className="text-xs font-medium truncate">{group.title}</span>
                    <span className="study-library-browse-match-badge ml-auto">{group.count}×</span>
                  </div>
                  <ul>
                    {group.hits.slice(0, 6).map((hit, i) => (
                      <li key={`${hit.topic_id}-${hit.match_kind}-${i}`}>
                        <button
                          type="button"
                          className="study-library-search-dropdown-item"
                          onClick={() => onOpenLibraryHit(hit.relative_path)}
                        >
                          <span className="text-[10px] uppercase tracking-wide text-muted-foreground shrink-0">
                            {hit.match_kind}
                          </span>
                          {hit.topic_id ? (
                            <code className="text-[10px] text-primary shrink-0">{hit.topic_id}</code>
                          ) : null}
                          <span className="text-xs truncate">{hit.label || hit.snippet}</span>
                        </button>
                      </li>
                    ))}
                  </ul>
                </li>
              ))}
            </ul>
          )}
          {scope === "library" && libraryLoading ? (
            <p className="text-[10px] text-muted-foreground text-center py-1">
              <ChevronDown className="w-3 h-3 inline animate-pulse" /> still searching…
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
