import { useState, useEffect, useRef, useCallback } from "react";
import { Link } from "react-router";
import {
  Clock, MessageSquare, Users, GripVertical,
  Settings2, X, Eye, EyeOff, Maximize2, Minimize2,
  ChevronLeft, ChevronRight, LayoutGrid, Sparkles, Timer
} from "lucide-react";
import { Card } from "../app/components/ui/card";
import { useStudySession } from "../context/StudySessionContext";
import { usePlugins } from "../plugins/registry";
import type { PluginWidget } from "../plugins/types";
import { DayTimeTracker } from "../features/math/components/DayTimeTracker";

// ─── Per-widget saved state ────────────────────────────────────────────────
interface WidgetState {
  colSpan: 1 | 2;
  rowSpan: 1 | 2;
  hidden: boolean;
}

type WidgetStateMap = Record<string, WidgetState>;

const LS_WIDGET_STATE = "dashboard:widget_state";
const LS_WIDGET_ORDER = "dashboard:widget_order";

function loadWidgetState(): WidgetStateMap {
  try {
    const s = localStorage.getItem(LS_WIDGET_STATE);
    return s ? JSON.parse(s) : {};
  } catch { return {}; }
}
function saveWidgetState(m: WidgetStateMap) {
  localStorage.setItem(LS_WIDGET_STATE, JSON.stringify(m));
}

// ─── Core widgets (always present, not from a plugin) ─────────────────────
const CORE_WIDGETS: PluginWidget[] = [
  {
    id: "life-clock",
    type: "info",
    title: "24-hour life clock",
    description: "Track how your day is unfolding",
    icon: Timer,
    accent: "from-indigo-500/20 to-violet-500/10",
    defaultColSpan: 2,
    defaultRowSpan: 2,
    component: <DayTimeTracker compact />,
  },
  {
    id: "study-time",
    type: "info",
    title: "Study Time & Focus",
    description: "Your focus is up 15% compared to yesterday. Keep it up!",
    content: "0m today",
    icon: Clock,
    accent: "from-amber-500/20 to-orange-500/10",
  },
  {
    id: "ai-comments",
    type: "info",
    title: "AI Review",
    description: "You completed 45 vocabulary questions.",
    content: "Excellent Retention",
    icon: MessageSquare,
    accent: "from-blue-500/20 to-cyan-500/10",
  },
  {
    id: "community",
    type: "info",
    title: "Community",
    description: "3 friends are currently studying.",
    content: "Join Room",
    icon: Users,
    accent: "from-rose-500/20 to-pink-500/10",
  },
];

// ─── Customizer Drawer ────────────────────────────────────────────────────
interface CustomizerProps {
  open: boolean;
  onClose: () => void;
  widgets: PluginWidget[];
  stateMap: WidgetStateMap;
  onToggleHide: (id: string) => void;
  onColSpan: (id: string, v: 1 | 2) => void;
  onRowSpan: (id: string, v: 1 | 2) => void;
}

function CustomizerDrawer({
  open, onClose, widgets, stateMap, onToggleHide, onColSpan, onRowSpan,
}: CustomizerProps) {
  return (
    <>
      {/* Backdrop */}
      {open && (
        <div
          className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm"
          onClick={onClose}
        />
      )}

      {/* Slide-in panel */}
      <aside
        className={`
          fixed top-0 right-0 z-50 h-full w-80 flex flex-col
          gloss-sidebar border-l border-border/50 shadow-2xl
          transition-transform duration-300 ease-in-out
          ${open ? "translate-x-0" : "translate-x-full"}
        `}
      >
        <div className="flex items-center justify-between p-4 border-b border-border/50 shrink-0">
          <div className="flex items-center gap-2">
            <LayoutGrid className="w-5 h-5 text-primary" />
            <span className="font-semibold">Customize Dashboard</span>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-accent/70 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          <p className="text-xs text-muted-foreground mb-4">
            Show/hide widgets and set their size. Changes apply instantly.
          </p>

          {widgets.map((w) => {
            const st = stateMap[w.id] ?? { colSpan: w.defaultColSpan ?? 1, rowSpan: w.defaultRowSpan ?? 1, hidden: false };
            const Icon = w.icon;
            return (
              <div
                key={w.id}
                className={`rounded-xl border p-3 space-y-3 transition-opacity ${
                  st.hidden ? "opacity-50 border-border/30" : "border-border/60"
                }`}
              >
                {/* Header row */}
                <div className="flex items-center gap-2">
                  <div className="w-7 h-7 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
                    <Icon className="w-3.5 h-3.5 text-primary" />
                  </div>
                  <span className="text-sm font-medium flex-1 truncate">{w.title}</span>
                  <button
                    onClick={() => onToggleHide(w.id)}
                    className={`p-1.5 rounded-lg transition-colors ${
                      st.hidden
                        ? "text-muted-foreground hover:text-foreground hover:bg-accent/50"
                        : "text-primary hover:bg-primary/10"
                    }`}
                    title={st.hidden ? "Show widget" : "Hide widget"}
                  >
                    {st.hidden ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>

                {/* Size controls */}
                {!st.hidden && (
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div>
                      <p className="text-muted-foreground mb-1">Width</p>
                      <div className="flex rounded-lg overflow-hidden border border-border/50">
                        {([1, 2] as const).map((v) => (
                          <button
                            key={v}
                            onClick={() => onColSpan(w.id, v)}
                            className={`flex-1 py-1 transition-colors ${
                              st.colSpan === v
                                ? "bg-primary text-primary-foreground"
                                : "hover:bg-accent/60 text-muted-foreground"
                            }`}
                          >
                            {v === 1 ? "Normal" : "Wide"}
                          </button>
                        ))}
                      </div>
                    </div>
                    <div>
                      <p className="text-muted-foreground mb-1">Height</p>
                      <div className="flex rounded-lg overflow-hidden border border-border/50">
                        {([1, 2] as const).map((v) => (
                          <button
                            key={v}
                            onClick={() => onRowSpan(w.id, v)}
                            className={`flex-1 py-1 transition-colors ${
                              st.rowSpan === v
                                ? "bg-primary text-primary-foreground"
                                : "hover:bg-accent/60 text-muted-foreground"
                            }`}
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

        <div className="p-4 border-t border-border/50 shrink-0">
          <p className="text-[10px] text-muted-foreground text-center">
            Add/remove entire features via{" "}
            <Link to="/settings/plugins" onClick={onClose} className="text-primary underline">
              Plugin Manager
            </Link>
          </p>
        </div>
      </aside>
    </>
  );
}

// ─── Main HomePage ────────────────────────────────────────────────────────
export function HomePage() {
  const [allWidgets, setAllWidgets] = useState<PluginWidget[]>([]);
  const [draggedIdx, setDraggedIdx] = useState<number | null>(null);
  const [customizerOpen, setCustomizerOpen] = useState(false);
  const [stateMap, setStateMap] = useState<WidgetStateMap>({});

  const { sessionData, diagnosticsSummary } = useStudySession();
  const { getWidgets, isLoaded } = usePlugins();

  // Build widget list once plugins are loaded
  useEffect(() => {
    if (!isLoaded) return;
    const available = [...CORE_WIDGETS, ...getWidgets()];

    // Restore order
    try {
      const savedOrder = localStorage.getItem(LS_WIDGET_ORDER);
      if (savedOrder) {
        const ids = JSON.parse(savedOrder) as string[];
        const ordered = ids
          .map((id) => available.find((w) => w.id === id))
          .filter(Boolean) as PluginWidget[];
        const missing = available.filter((w) => !ids.includes(w.id));
        setAllWidgets([...ordered, ...missing]);
      } else {
        setAllWidgets(available);
      }
    } catch {
      setAllWidgets(available);
    }

    setStateMap(loadWidgetState());
  }, [isLoaded]); // eslint-disable-line

  // Dynamic core widget data
  const displayWidgets = allWidgets.map((w) => {
    if (w.id === "study-time") {
      const d = diagnosticsSummary.duration;
      return { ...w, content: `${Math.floor(d / 60)}m ${Math.floor(d % 60)}s today` };
    }
    if (w.id === "ai-comments") {
      const perf = diagnosticsSummary.overallPerformance;
      const msg =
        perf === "excellent" ? "Looking great — keep the momentum!" :
        perf === "good" ? "Good progress, stay focused!" :
        "Take a breath, you've got this.";
      return {
        ...w,
        description: `${msg} ${sessionData.interventionCount} AI hints so far.`,
        content: perf === "excellent" ? "Excellent" : "Keep Going",
      };
    }
    return w;
  });

  // Customizer helpers
  const updateState = useCallback((id: string, patch: Partial<WidgetState>) => {
    setStateMap((prev) => {
      const defaults = allWidgets.find((w) => w.id === id);
      const current = prev[id] ?? {
        colSpan: defaults?.defaultColSpan ?? 1,
        rowSpan: defaults?.defaultRowSpan ?? 1,
        hidden: false,
      };
      const next = { ...prev, [id]: { ...current, ...patch } };
      saveWidgetState(next);
      return next;
    });
  }, [allWidgets]);

  const toggleHide = (id: string) => {
    const cur = stateMap[id]?.hidden ?? false;
    updateState(id, { hidden: !cur });
  };
  const setColSpan = (id: string, v: 1 | 2) => updateState(id, { colSpan: v });
  const setRowSpan = (id: string, v: 1 | 2) => updateState(id, { rowSpan: v });

  // Drag-to-reorder
  const handleDragStart = (e: React.DragEvent, idx: number) => {
    setDraggedIdx(idx);
    e.dataTransfer.effectAllowed = "move";
    (e.currentTarget as HTMLElement).style.opacity = "0.4";
  };
  const handleDragEnd = (e: React.DragEvent) => {
    setDraggedIdx(null);
    (e.currentTarget as HTMLElement).style.opacity = "1";
    localStorage.setItem(LS_WIDGET_ORDER, JSON.stringify(allWidgets.map((w) => w.id)));
  };
  const handleDragOver = (e: React.DragEvent, idx: number) => {
    e.preventDefault();
    if (draggedIdx === null || draggedIdx === idx) return;
    setAllWidgets((prev) => {
      const next = [...prev];
      const [item] = next.splice(draggedIdx, 1);
      next.splice(idx, 0, item);
      setDraggedIdx(idx);
      return next;
    });
  };

  if (!isLoaded) return null;

  const visibleWidgets = displayWidgets.filter((w) => !(stateMap[w.id]?.hidden));

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* ── Header bar ────────────────────────────── */}
      <div className="flex items-center justify-between px-4 pt-4 pb-3 shrink-0">
        <div>
          <div className="flex items-center gap-2 text-primary mb-0.5">
            <Sparkles className="w-4 h-4" />
            <span className="text-xs font-medium uppercase tracking-wider">Dashboard</span>
          </div>
          <h1 className="text-xl font-bold">Welcome back</h1>
        </div>

        {/* Customise button — always visible */}
        <button
          id="dashboard-customize-btn"
          onClick={() => setCustomizerOpen(true)}
          className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium
                     gloss-panel border border-border/50 hover:border-primary/50
                     hover:text-primary transition-all duration-200"
        >
          <LayoutGrid className="w-4 h-4" />
          Customize
        </button>
      </div>

      {/* ── Responsive full-bleed grid ───────────── */}
      <div
        className="flex-1 overflow-y-auto px-4 pb-4"
        style={{ minHeight: 0 }}
      >
        <div
          className="dashboard-grid"
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(min(100%, 320px), 1fr))",
            gridAutoRows: "minmax(180px, auto)",
            gap: "1rem",
            alignContent: "start",
          }}
        >
          {visibleWidgets.map((widget, idx) => {
            const st = stateMap[widget.id] ?? {
              colSpan: widget.defaultColSpan ?? 1,
              rowSpan: widget.defaultRowSpan ?? 1,
              hidden: false,
            };
            const { id, title, type, content, icon: Icon, accent, to, component, description } = widget;

            const cardBody = (
              <Card
                className={`
                  gloss-panel h-full flex flex-col p-5
                  bg-gradient-to-br ${accent}
                  group relative transition-all duration-200
                `}
              >
                {/* Drag handle — top right on hover */}
                <div
                  className="absolute top-3 right-3 opacity-0 group-hover:opacity-100
                              cursor-grab active:cursor-grabbing text-muted-foreground
                              hover:text-foreground transition-opacity"
                >
                  <GripVertical className="w-4 h-4" />
                </div>

                {/* Icon + title */}
                <div className="flex items-start gap-3 mb-3">
                  <div className="w-9 h-9 rounded-xl bg-background/30 flex items-center justify-center shrink-0">
                    <Icon className="w-5 h-5 text-foreground/90" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="font-semibold text-base leading-tight truncate">{title}</h3>
                    {type === "info" && content && (
                      <span className="text-xs px-1.5 py-0.5 bg-background/40 rounded mt-1 inline-block">
                        {content}
                      </span>
                    )}
                  </div>
                </div>

                {/* Widget body */}
                <div className="flex-1 min-h-0 overflow-hidden">
                  {component
                    ? component
                    : <p className="text-sm text-muted-foreground leading-relaxed">{description}</p>
                  }
                </div>

                {/* Resize corner */}
                <div
                  className="absolute bottom-2 right-2 opacity-0 group-hover:opacity-100
                              flex gap-1 transition-opacity"
                >
                  <button
                    onClick={(e) => { e.preventDefault(); e.stopPropagation(); setColSpan(id, st.colSpan === 1 ? 2 : 1); }}
                    className="p-1 rounded bg-background/50 hover:bg-background/80 text-muted-foreground hover:text-foreground transition-colors"
                    title={st.colSpan === 2 ? "Make narrow" : "Make wide"}
                  >
                    {st.colSpan === 2
                      ? <ChevronLeft className="w-3 h-3" />
                      : <ChevronRight className="w-3 h-3" />}
                  </button>
                  <button
                    onClick={(e) => { e.preventDefault(); e.stopPropagation(); setRowSpan(id, st.rowSpan === 1 ? 2 : 1); }}
                    className="p-1 rounded bg-background/50 hover:bg-background/80 text-muted-foreground hover:text-foreground transition-colors"
                    title={st.rowSpan === 2 ? "Make short" : "Make tall"}
                  >
                    {st.rowSpan === 2
                      ? <Minimize2 className="w-3 h-3" />
                      : <Maximize2 className="w-3 h-3" />}
                  </button>
                </div>
              </Card>
            );

            return (
              <div
                key={id}
                draggable
                onDragStart={(e) => handleDragStart(e, idx)}
                onDragEnd={handleDragEnd}
                onDragOver={(e) => handleDragOver(e, idx)}
                style={{
                  gridColumn: `span ${st.colSpan}`,
                  gridRow: `span ${st.rowSpan}`,
                  minWidth: 0,
                }}
                className="transition-all duration-300 cursor-grab active:cursor-grabbing"
              >
                {to ? (
                  <Link to={to} className="block h-full">
                    {cardBody}
                  </Link>
                ) : (
                  <div className="h-full">{cardBody}</div>
                )}
              </div>
            );
          })}

          {/* Empty state when all widgets hidden */}
          {visibleWidgets.length === 0 && (
            <div
              className="col-span-full flex flex-col items-center justify-center py-24 text-center text-muted-foreground"
              style={{ gridColumn: "1 / -1" }}
            >
              <LayoutGrid className="w-12 h-12 mb-4 opacity-30" />
              <p className="text-lg font-medium mb-2">All widgets are hidden</p>
              <p className="text-sm mb-4">Click <strong>Customize</strong> to show them again.</p>
              <button
                onClick={() => setCustomizerOpen(true)}
                className="px-4 py-2 rounded-xl bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors"
              >
                Open Customizer
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Customizer drawer */}
      <CustomizerDrawer
        open={customizerOpen}
        onClose={() => setCustomizerOpen(false)}
        widgets={allWidgets}
        stateMap={stateMap}
        onToggleHide={toggleHide}
        onColSpan={setColSpan}
        onRowSpan={setRowSpan}
      />
    </div>
  );
}
