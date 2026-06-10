import { useMemo, useState } from "react";
import { LayoutGrid, Plus, Search, X } from "lucide-react";
import type { PluginWidget } from "../../plugins/types";
import {
  OPTIONAL_WIDGET_CATALOG,
  type CatalogCategory,
  type CatalogEntry,
} from "./widgetCatalog";

const CATEGORIES: { id: CatalogCategory; label: string }[] = [
  { id: "all", label: "All" },
  { id: "study", label: "Study" },
  { id: "math", label: "Math" },
  { id: "health", label: "Health" },
];

interface WidgetPickerModalProps {
  open: boolean;
  onClose: () => void;
  onAdd: (widget: CatalogEntry) => void;
  activeIds: Set<string>;
  extraCatalog?: PluginWidget[];
}

export function WidgetPickerModal({
  open,
  onClose,
  onAdd,
  activeIds,
  extraCatalog = [],
}: WidgetPickerModalProps) {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState<CatalogCategory>("all");

  const catalog = useMemo(() => {
    const extras = extraCatalog.filter((w) => w.catalogOnly) as CatalogEntry[];
    const merged = [...OPTIONAL_WIDGET_CATALOG];
    for (const e of extras) {
      if (!merged.some((m) => m.id === e.id)) merged.push(e);
    }
    return merged;
  }, [extraCatalog]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return catalog.filter((w) => {
      if (category !== "all" && w.category !== category) return false;
      if (!q) return true;
      return (
        w.title.toLowerCase().includes(q) ||
        w.description.toLowerCase().includes(q) ||
        w.id.includes(q)
      );
    });
  }, [catalog, query, category]);

  if (!open) return null;

  return (
    <>
      <div
        className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden
      />
      <div
        role="dialog"
        aria-modal
        aria-labelledby="widget-picker-title"
        className="fixed left-1/2 top-1/2 z-50 w-full max-w-lg -translate-x-1/2 -translate-y-1/2
                   gloss-panel border border-border/60 rounded-2xl shadow-2xl flex flex-col max-h-[85vh]"
      >
        <div className="flex items-center justify-between p-4 border-b border-border/50 shrink-0">
          <div className="flex items-center gap-2">
            <LayoutGrid className="w-5 h-5 text-primary" />
            <h2 id="widget-picker-title" className="font-semibold">
              Add Widget
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-accent/70 transition-colors"
            aria-label="Close"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-4 space-y-3 shrink-0">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search widgets…"
              className="w-full pl-9 pr-3 py-2 rounded-lg border border-border/60 bg-background/50 text-sm"
            />
          </div>
          <div className="flex gap-1 flex-wrap">
            {CATEGORIES.map((c) => (
              <button
                key={c.id}
                type="button"
                onClick={() => setCategory(c.id)}
                className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                  category === c.id
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted/50 text-muted-foreground hover:text-foreground"
                }`}
              >
                {c.label}
              </button>
            ))}
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-4 pb-4 space-y-2 min-h-0">
          {filtered.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-8">No widgets match.</p>
          ) : (
            filtered.map((w) => {
              const Icon = w.icon;
              const added = activeIds.has(w.id);
              return (
                <div
                  key={w.id}
                  className="flex items-center gap-3 rounded-xl border border-border/50 p-3"
                >
                  <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
                    <Icon className="w-4 h-4 text-primary" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{w.title}</p>
                    <p className="text-xs text-muted-foreground line-clamp-2">{w.description}</p>
                  </div>
                  <button
                    type="button"
                    disabled={added}
                    onClick={() => {
                      onAdd(w);
                      onClose();
                    }}
                    className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium
                               bg-primary text-primary-foreground disabled:opacity-40 disabled:cursor-not-allowed
                               hover:bg-primary/90 transition-colors shrink-0"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    {added ? "Added" : "Add"}
                  </button>
                </div>
              );
            })
          )}
        </div>
      </div>
    </>
  );
}
