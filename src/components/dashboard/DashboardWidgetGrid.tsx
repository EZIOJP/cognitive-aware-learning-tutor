import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router";
import {
  GripVertical,
  LayoutGrid,
  X,
  Eye,
  EyeOff,
  ChevronLeft,
  ChevronRight,
  Maximize2,
  Minimize2,
} from "lucide-react";
import { Card } from "../../app/components/ui/card";
import type { DashboardWidget, WidgetState, WidgetStateMap } from "./dashboardWidgetUtils";
import {
  loadWidgetOrder,
  loadWidgetState,
  saveWidgetState,
} from "./dashboardWidgetUtils";

interface CustomizerProps {
  open: boolean;
  onClose: () => void;
  widgets: DashboardWidget[];
  stateMap: WidgetStateMap;
  onToggleHide: (id: string) => void;
  onColSpan: (id: string, v: 1 | 2) => void;
  onRowSpan: (id: string, v: 1 | 2) => void;
  onReset: () => void;
}

function CustomizerDrawer({
  open,
  onClose,
  widgets,
  stateMap,
  onToggleHide,
  onColSpan,
  onRowSpan,
  onReset,
}: CustomizerProps) {
  return (
    <>
      {open && (
        <div className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm" onClick={onClose} />
      )}
      <aside
        className={`fixed top-0 right-0 z-50 h-full w-80 flex flex-col gloss-sidebar border-l border-border/50 shadow-2xl transition-transform duration-300 ${
          open ? "translate-x-0" : "translate-x-full"
        }`}
      >
        <div className="flex items-center justify-between p-4 border-b border-border/50 shrink-0">
          <div className="flex items-center gap-2">
            <LayoutGrid className="w-5 h-5 text-primary" />
            <span className="font-semibold">Edit widgets</span>
          </div>
          <button type="button" onClick={onClose} className="p-1.5 rounded-lg hover:bg-accent/70">
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          <p className="text-xs text-muted-foreground">
            Show, hide, resize, or drag widgets on the grid.
          </p>
          <button
            type="button"
            onClick={onReset}
            className="w-full text-xs py-2 rounded-lg border hover:bg-accent/50"
          >
            Reset all widgets
          </button>
          {widgets.map((w) => {
            const st = stateMap[w.id] ?? {
              colSpan: w.defaultColSpan ?? 1,
              rowSpan: w.defaultRowSpan ?? 1,
              hidden: false,
            };
            const Icon = w.icon;
            return (
              <div
                key={w.id}
                className={`rounded-xl border p-3 space-y-3 ${st.hidden ? "opacity-50" : ""}`}
              >
                <div className="flex items-center gap-2">
                  <Icon className="w-4 h-4 text-primary shrink-0" />
                  <span className="text-sm font-medium flex-1 truncate">{w.title}</span>
                  <button type="button" onClick={() => onToggleHide(w.id)} className="p-1.5 rounded-lg hover:bg-accent/50">
                    {st.hidden ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
                {!st.hidden && (
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div>
                      <p className="text-muted-foreground mb-1">Width</p>
                      <div className="flex rounded-lg overflow-hidden border">
                        {([1, 2] as const).map((v) => (
                          <button
                            key={v}
                            type="button"
                            onClick={() => onColSpan(w.id, v)}
                            className={`flex-1 py-1 ${st.colSpan === v ? "bg-primary text-primary-foreground" : "hover:bg-accent/60"}`}
                          >
                            {v === 1 ? "Normal" : "Wide"}
                          </button>
                        ))}
                      </div>
                    </div>
                    <div>
                      <p className="text-muted-foreground mb-1">Height</p>
                      <div className="flex rounded-lg overflow-hidden border">
                        {([1, 2] as const).map((v) => (
                          <button
                            key={v}
                            type="button"
                            onClick={() => onRowSpan(w.id, v)}
                            className={`flex-1 py-1 ${st.rowSpan === v ? "bg-primary text-primary-foreground" : "hover:bg-accent/60"}`}
                          >
                            {v === 1 ? "Short" : "Tall"}
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </aside>
    </>
  );
}

interface DashboardWidgetGridProps {
  storageKey: string;
  title: string;
  subtitle?: string;
  widgets: DashboardWidget[];
  headerExtra?: React.ReactNode;
}

function mergeWidgetDefs(order: DashboardWidget[], defs: DashboardWidget[]): DashboardWidget[] {
  const byId = new Map(defs.map((w) => [w.id, w]));
  const seen = new Set<string>();
  const merged: DashboardWidget[] = [];

  for (const w of order) {
    const fresh = byId.get(w.id);
    if (fresh) {
      merged.push(fresh);
      seen.add(w.id);
    }
  }
  for (const w of defs) {
    if (!seen.has(w.id)) merged.push(w);
  }
  return merged;
}

export function DashboardWidgetGrid({
  storageKey,
  title,
  subtitle,
  widgets: widgetDefs,
  headerExtra,
}: DashboardWidgetGridProps) {
  const defsRef = useRef(widgetDefs);
  defsRef.current = widgetDefs;

  const [orderIds, setOrderIds] = useState<string[]>(() =>
    widgetDefs.map((w) => w.id)
  );
  const [stateMap, setStateMap] = useState<WidgetStateMap>(() =>
    loadWidgetState(storageKey)
  );
  const [customizerOpen, setCustomizerOpen] = useState(false);
  const [draggedIdx, setDraggedIdx] = useState<number | null>(null);
  const [initialized, setInitialized] = useState(false);

  useEffect(() => {
    const ordered = loadWidgetOrder(storageKey, widgetDefs);
    setOrderIds(ordered.map((w) => w.id));
    setStateMap(loadWidgetState(storageKey));
    setInitialized(true);
  }, [storageKey]); // eslint-disable-line react-hooks/exhaustive-deps -- load persisted layout once per dashboard

  const widgets = mergeWidgetDefs(
    orderIds.map((id) => ({ id } as DashboardWidget)),
    defsRef.current
  );

  const updateState = useCallback(
    (id: string, patch: Partial<WidgetState>) => {
      setStateMap((prev) => {
        const w = defsRef.current.find((x) => x.id === id);
        const current = prev[id] ?? {
          colSpan: w?.defaultColSpan ?? 1,
          rowSpan: w?.defaultRowSpan ?? 1,
          hidden: false,
        };
        const next = { ...prev, [id]: { ...current, ...patch } };
        saveWidgetState(storageKey, next);
        return next;
      });
    },
    [storageKey]
  );

  const resetWidgets = () => {
    localStorage.removeItem(`${storageKey}:state`);
    localStorage.removeItem(`${storageKey}:order`);
    setOrderIds(defsRef.current.map((w) => w.id));
    setStateMap({});
  };

  const visible = widgets.filter((w) => !stateMap[w.id]?.hidden);

  if (!initialized) {
    return (
      <div className="h-full flex items-center justify-center text-sm text-muted-foreground">
        Loading dashboard…
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col overflow-hidden min-h-0">
      <div className="flex items-center justify-between px-1 pt-1 pb-3 shrink-0 gap-3">
        <div>
          <h1 className="text-xl font-bold">{title}</h1>
          {subtitle ? <p className="text-sm text-muted-foreground">{subtitle}</p> : null}
        </div>
        <div className="flex items-center gap-2">
          {headerExtra}
          <button
            type="button"
            onClick={() => setCustomizerOpen(true)}
            className="flex items-center gap-2 px-3 py-2 rounded-xl text-sm gloss-panel border hover:border-primary/50 hover:text-primary"
          >
            <LayoutGrid className="w-4 h-4" />
            Edit widgets
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto min-h-0 pb-4">
        {visible.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-center text-muted-foreground">
            <LayoutGrid className="w-10 h-10 mb-3 opacity-40" />
            <p className="font-medium mb-1">All widgets are hidden</p>
            <button
              type="button"
              onClick={() => setCustomizerOpen(true)}
              className="mt-3 px-4 py-2 rounded-xl bg-primary text-primary-foreground text-sm"
            >
              Edit widgets
            </button>
          </div>
        ) : (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(min(100%, 280px), 1fr))",
              gridAutoRows: "minmax(140px, auto)",
              gap: "1rem",
            }}
          >
            {visible.map((widget, idx) => {
              const st = stateMap[widget.id] ?? {
                colSpan: widget.defaultColSpan ?? 1,
                rowSpan: widget.defaultRowSpan ?? 1,
                hidden: false,
              };
              const Icon = widget.icon;
              const inner = (
                <Card
                  className={`gloss-panel h-full flex flex-col p-4 bg-gradient-to-br ${widget.accent} group relative`}
                >
                  <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 cursor-grab">
                    <GripVertical className="w-4 h-4 text-muted-foreground" />
                  </div>
                  <div className="flex items-center gap-2 mb-2 shrink-0">
                    <Icon className="w-4 h-4" />
                    <h3 className="font-semibold text-sm truncate">{widget.title}</h3>
                  </div>
                  <div className="flex-1 min-h-0 overflow-auto">{widget.component}</div>
                  <div className="absolute bottom-2 right-2 opacity-0 group-hover:opacity-100 flex gap-1">
                    <button
                      type="button"
                      onClick={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        updateState(widget.id, { colSpan: st.colSpan === 1 ? 2 : 1 });
                      }}
                      className="p-1 rounded bg-background/60"
                    >
                      {st.colSpan === 2 ? <ChevronLeft className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                    </button>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        updateState(widget.id, { rowSpan: st.rowSpan === 1 ? 2 : 1 });
                      }}
                      className="p-1 rounded bg-background/60"
                    >
                      {st.rowSpan === 2 ? <Minimize2 className="w-3 h-3" /> : <Maximize2 className="w-3 h-3" />}
                    </button>
                  </div>
                </Card>
              );

              return (
                <div
                  key={widget.id}
                  draggable
                  onDragStart={() => setDraggedIdx(idx)}
                  onDragEnd={() => {
                    setDraggedIdx(null);
                    setOrderIds((current) => {
                      localStorage.setItem(`${storageKey}:order`, JSON.stringify(current));
                      return current;
                    });
                  }}
                  onDragOver={(e) => {
                    e.preventDefault();
                    if (draggedIdx === null || draggedIdx === idx) return;
                    const draggedId = visible[draggedIdx]?.id;
                    const targetId = visible[idx]?.id;
                    if (!draggedId || !targetId || draggedId === targetId) return;
                    setOrderIds((prev) => {
                      const next = [...prev];
                      const from = next.indexOf(draggedId);
                      const to = next.indexOf(targetId);
                      if (from < 0 || to < 0) return prev;
                      next.splice(from, 1);
                      next.splice(to, 0, draggedId);
                      return next;
                    });
                    setDraggedIdx(idx);
                  }}
                  style={{ gridColumn: `span ${st.colSpan}`, gridRow: `span ${st.rowSpan}` }}
                  className="min-w-0"
                >
                  {widget.to ? (
                    <Link to={widget.to} className="block h-full">
                      {inner}
                    </Link>
                  ) : (
                    inner
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      <CustomizerDrawer
        open={customizerOpen}
        onClose={() => setCustomizerOpen(false)}
        widgets={widgets}
        stateMap={stateMap}
        onToggleHide={(id) => updateState(id, { hidden: !(stateMap[id]?.hidden ?? false) })}
        onColSpan={(id, v) => updateState(id, { colSpan: v })}
        onRowSpan={(id, v) => updateState(id, { rowSpan: v })}
        onReset={resetWidgets}
      />
    </div>
  );
}
