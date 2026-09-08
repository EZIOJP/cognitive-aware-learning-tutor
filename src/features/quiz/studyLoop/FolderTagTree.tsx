import { useMemo, useState } from "react";
import { ChevronDown, ChevronRight, Folder } from "lucide-react";
import type { StudyLoopTag } from "../../../api/globalQuizClient";
import { groupTagsByFolder } from "./learnFolders";

type Props = {
  tags: StudyLoopTag[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  /** Prefer tags with read cards when true. */
  readCardsOnly?: boolean;
  className?: string;
};

export function FolderTagTree({
  tags,
  selectedId,
  onSelect,
  readCardsOnly = false,
  className = "",
}: Props) {
  const filtered = useMemo(() => {
    const rows = readCardsOnly ? tags.filter((t) => Boolean(t.has_read_card)) : tags;
    return groupTagsByFolder(rows);
  }, [tags, readCardsOnly]);

  const [open, setOpen] = useState<Record<string, boolean>>(() => {
    const init: Record<string, boolean> = {};
    for (const g of groupTagsByFolder(tags)) {
      init[g.id] = g.id === "math-core" || g.id === "numpy" || g.id === "pandas";
    }
    return init;
  });

  if (filtered.length === 0) {
    return (
      <p className="text-xs text-muted-foreground py-2">
        {readCardsOnly ? "No read cards indexed yet." : "No tags."}
      </p>
    );
  }

  return (
    <div className={`space-y-1 ${className}`}>
      {filtered.map((folder) => {
        const isOpen = open[folder.id] !== false;
        return (
          <div key={folder.id} className="rounded-lg border border-border/40 overflow-hidden">
            <button
              type="button"
              className="w-full flex items-center gap-1.5 px-2.5 py-2 text-left text-sm font-medium bg-background/40 hover:bg-muted/40"
              onClick={() => setOpen((prev) => ({ ...prev, [folder.id]: !isOpen }))}
            >
              {isOpen ? (
                <ChevronDown className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
              ) : (
                <ChevronRight className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
              )}
              <Folder className="h-3.5 w-3.5 text-primary shrink-0" />
              <span className="truncate">{folder.label}</span>
              <span className="ml-auto text-[10px] text-muted-foreground tabular-nums">
                {folder.tags.length}
              </span>
            </button>
            {isOpen ? (
              <ul className="max-h-56 overflow-y-auto border-t border-border/30">
                {folder.tags.map((tag) => {
                  const id = String(tag.id);
                  const active = id === selectedId;
                  return (
                    <li key={id}>
                      <button
                        type="button"
                        onClick={() => onSelect(id)}
                        className={`w-full text-left px-3 py-1.5 text-sm border-l-2 transition ${
                          active
                            ? "border-primary bg-primary/10"
                            : "border-transparent hover:bg-muted/30"
                        }`}
                      >
                        <span className="font-mono text-xs">{id}</span>
                        <span className="block text-[10px] text-muted-foreground truncate">
                          {String(tag.label || id)}
                          {Number(tag.question_count || 0) > 0
                            ? ` · ${tag.question_count}Q`
                            : ""}
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}
