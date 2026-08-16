import { useCallback, useEffect, useState } from "react";
import {
  ChevronDown,
  ChevronUp,
  Coffee,
  Loader2,
  Pencil,
  Plus,
  RefreshCw,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";
import {
  applyRoutines,
  blockColor,
  createRoutine,
  deleteRoutine,
  fetchRoutines,
  seedDefaultRoutines,
  updateRoutine,
  type PlannerRoutine,
} from "../../api/plannerClient";
import { cn } from "../../app/components/ui/utils";
import { setRoutineDragData, clearRoutineDragActive } from "./routineDrag";

const DAY_OPTS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"] as const;
const DAY_LABELS = ["M", "T", "W", "T", "F", "S", "S"] as const;
const CATEGORIES = ["spiritual", "food", "personal", "break", "study"] as const;

type Draft = {
  title: string;
  start_time: string;
  end_time: string;
  duration_minutes: number;
  category: string;
  days: string[];
  enabled: boolean;
};

function parseHm(t: string): number {
  const [h, m] = t.split(":").map((x) => Number(x) || 0);
  return h * 60 + m;
}

function formatHm(total: number): string {
  const n = ((total % (24 * 60)) + 24 * 60) % (24 * 60);
  const h = Math.floor(n / 60);
  const m = n % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

function minutesBetween(start: string, end: string): number {
  let d = parseHm(end) - parseHm(start);
  if (d <= 0) d += 24 * 60;
  return Math.max(1, d);
}

function endFromStart(start: string, mins: number): string {
  return formatHm(parseHm(start) + Math.max(1, mins));
}

function draftFromRoutine(r: PlannerRoutine): Draft {
  const start = r.start_time || "07:00";
  const end = r.end_time || endFromStart(start, r.duration_minutes || 30);
  return {
    title: r.title,
    start_time: start,
    end_time: end,
    duration_minutes: r.duration_minutes || minutesBetween(start, end),
    category: r.category || "personal",
    days: r.days?.length ? [...r.days] : [...DAY_OPTS],
    enabled: r.enabled,
  };
}

function emptyDraft(): Draft {
  return {
    title: "",
    start_time: "07:00",
    end_time: "07:30",
    duration_minutes: 30,
    category: "personal",
    days: [...DAY_OPTS],
    enabled: true,
  };
}

function DurationStepper({
  value,
  onChange,
}: {
  value: number;
  onChange: (n: number) => void;
}) {
  const bump = (dir: 1 | -1) => onChange(Math.min(240, Math.max(5, value + dir * 5)));
  return (
    <div className="inline-flex items-stretch rounded border border-white/10 bg-black/30 overflow-hidden h-8">
      <span className="min-w-[2.5rem] px-1.5 flex items-center justify-center font-mono tabular-nums text-xs text-foreground">
        {value}m
      </span>
      <div className="flex flex-col border-l border-white/10 w-5">
        <button
          type="button"
          aria-label="Increase duration"
          onClick={() => bump(1)}
          className="flex-1 flex items-center justify-center hover:bg-white/10"
        >
          <ChevronUp size={11} />
        </button>
        <button
          type="button"
          aria-label="Decrease duration"
          onClick={() => bump(-1)}
          className="flex-1 flex items-center justify-center border-t border-white/10 hover:bg-white/10"
        >
          <ChevronDown size={11} />
        </button>
      </div>
    </div>
  );
}

function DayToggles({
  days,
  onChange,
}: {
  days: string[];
  onChange: (days: string[]) => void;
}) {
  return (
    <div className="flex flex-wrap gap-1">
      {DAY_OPTS.map((d, i) => {
        const on = days.includes(d);
        return (
          <button
            key={d}
            type="button"
            onClick={() =>
              onChange(on ? days.filter((x) => x !== d) : [...days, d])
            }
            className={cn(
              "h-6 w-6 rounded text-[10px] font-medium",
              on
                ? "bg-violet-500/40 text-violet-100 border border-violet-400/40"
                : "bg-white/5 text-muted-foreground border border-white/10",
            )}
            title={d}
          >
            {DAY_LABELS[i]}
          </button>
        );
      })}
    </div>
  );
}

function RoutineEditor({
  draft,
  setDraft,
  onSave,
  onCancel,
  saving,
  saveLabel,
}: {
  draft: Draft;
  setDraft: (d: Draft) => void;
  onSave: () => void;
  onCancel: () => void;
  saving: boolean;
  saveLabel: string;
}) {
  const setStart = (start_time: string) => {
    setDraft({
      ...draft,
      start_time,
      end_time: endFromStart(start_time, draft.duration_minutes),
    });
  };
  const setDuration = (duration_minutes: number) => {
    setDraft({
      ...draft,
      duration_minutes,
      end_time: endFromStart(draft.start_time, duration_minutes),
    });
  };
  const setEnd = (end_time: string) => {
    setDraft({
      ...draft,
      end_time,
      duration_minutes: minutesBetween(draft.start_time, end_time),
    });
  };

  return (
    <div className="mt-2 space-y-2 rounded-lg border border-white/10 bg-black/25 p-3">
      <input
        className="w-full text-sm bg-black/30 border border-white/10 rounded px-2 py-1.5 text-foreground"
        placeholder="Title"
        value={draft.title}
        onChange={(e) => setDraft({ ...draft, title: e.target.value })}
      />
      <div className="flex flex-wrap items-end gap-2">
        <label className="text-[10px] text-muted-foreground">
          Start
          <input
            type="time"
            className="mt-0.5 block text-xs bg-black/30 border border-white/10 rounded px-2 py-1.5 h-8 text-foreground"
            value={draft.start_time}
            onChange={(e) => setStart(e.target.value)}
          />
        </label>
        <label className="text-[10px] text-muted-foreground">
          End
          <input
            type="time"
            className="mt-0.5 block text-xs bg-black/30 border border-white/10 rounded px-2 py-1.5 h-8 text-foreground"
            value={draft.end_time}
            onChange={(e) => setEnd(e.target.value)}
          />
        </label>
        <div className="text-[10px] text-muted-foreground">
          Duration
          <div className="mt-0.5">
            <DurationStepper value={draft.duration_minutes} onChange={setDuration} />
          </div>
        </div>
        <label className="text-[10px] text-muted-foreground">
          Category
          <select
            className="mt-0.5 block text-xs bg-black/30 border border-white/10 rounded px-2 py-1.5 h-8 text-foreground"
            value={draft.category}
            onChange={(e) => setDraft({ ...draft, category: e.target.value })}
          >
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div>
        <p className="text-[10px] text-muted-foreground mb-1">Days</p>
        <DayToggles days={draft.days} onChange={(days) => setDraft({ ...draft, days })} />
      </div>
      <div className="flex flex-wrap gap-2 pt-1">
        <button
          type="button"
          disabled={saving || !draft.title.trim()}
          onClick={onSave}
          className="px-3 py-1.5 rounded-lg bg-emerald-600/80 hover:bg-emerald-600 text-xs disabled:opacity-50"
        >
          {saving ? "Saving…" : saveLabel}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="px-3 py-1.5 rounded-lg border border-white/10 text-xs hover:bg-white/5"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

export function RoutinesPanel({
  onApplied,
  onRoutinesChange,
}: {
  onApplied?: () => void;
  onRoutinesChange?: (routines: PlannerRoutine[]) => void;
}) {
  const [routines, setRoutines] = useState<PlannerRoutine[]>([]);
  const [loading, setLoading] = useState(true);
  const [applying, setApplying] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showAdd, setShowAdd] = useState(false);
  const [addDraft, setAddDraft] = useState<Draft>(emptyDraft);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editDraft, setEditDraft] = useState<Draft | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const rows = await fetchRoutines();
      setRoutines(rows);
      onRoutinesChange?.(rows);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load routines");
    } finally {
      setLoading(false);
    }
  }, [onRoutinesChange]);

  useEffect(() => {
    void load();
  }, [load]);

  const sortedRoutines = [...routines].sort((a, b) => {
    const ta = parseHm(a.start_time || "00:00");
    const tb = parseHm(b.start_time || "00:00");
    if (ta !== tb) return ta - tb;
    return a.id - b.id;
  });

  const handleSeed = async () => {
    setError(null);
    try {
      const rows = await seedDefaultRoutines();
      setRoutines(rows);
      onRoutinesChange?.(rows);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Seed failed");
    }
  };

  const handleApply = async () => {
    setApplying(true);
    setError(null);
    try {
      const r = await applyRoutines(
        (() => {
          const t = new Date();
          const y = t.getFullYear();
          const m = String(t.getMonth() + 1).padStart(2, "0");
          const d = String(t.getDate()).padStart(2, "0");
          return `${y}-${m}-${d}`;
        })(),
      );
      onApplied?.();
      alert(`Added ${r.created} routine block(s) to today's planner.`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Apply failed");
    } finally {
      setApplying(false);
    }
  };

  const handleAdd = async () => {
    if (!addDraft.title.trim()) return;
    setSaving(true);
    setError(null);
    try {
      await createRoutine({
        title: addDraft.title.trim(),
        category: addDraft.category,
        start_time: addDraft.start_time,
        end_time: addDraft.end_time,
        days: addDraft.days,
      });
      setAddDraft(emptyDraft());
      setShowAdd(false);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Create failed");
    } finally {
      setSaving(false);
    }
  };

  const startEdit = (r: PlannerRoutine) => {
    setEditingId(r.id);
    setEditDraft(draftFromRoutine(r));
    setShowAdd(false);
  };

  const handleSaveEdit = async () => {
    if (editingId == null || !editDraft?.title.trim()) return;
    setSaving(true);
    setError(null);
    try {
      await updateRoutine(editingId, {
        title: editDraft.title.trim(),
        category: editDraft.category,
        start_time: editDraft.start_time,
        end_time: editDraft.end_time,
        duration_minutes: editDraft.duration_minutes,
        days: editDraft.days,
        enabled: editDraft.enabled,
      });
      setEditingId(null);
      setEditDraft(null);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Update failed");
    } finally {
      setSaving(false);
    }
  };

  const toggleEnabled = async (r: PlannerRoutine) => {
    try {
      await updateRoutine(r.id, { enabled: !r.enabled });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Update failed");
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm("Remove this routine?")) return;
    try {
      await deleteRoutine(id);
      if (editingId === id) {
        setEditingId(null);
        setEditDraft(null);
      }
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Delete failed");
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="font-semibold flex items-center gap-2">
          <Coffee size={16} className="text-amber-400" />
          Daily routines
        </h2>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            disabled={applying}
            onClick={() => void handleApply()}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-600/80 hover:bg-amber-600 text-xs disabled:opacity-50"
          >
            {applying ? <Loader2 size={13} className="animate-spin" /> : <RefreshCw size={13} />}
            Apply to today
          </button>
          {routines.length === 0 && (
            <button
              type="button"
              onClick={() => void handleSeed()}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-xs border border-white/10"
            >
              <Sparkles size={13} />
              Add defaults
            </button>
          )}
          <button
            type="button"
            onClick={() => {
              setShowAdd((v) => !v);
              setEditingId(null);
              setEditDraft(null);
              if (!showAdd) setAddDraft(emptyDraft());
            }}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-violet-600/80 hover:bg-violet-600 text-xs"
          >
            {showAdd ? <X size={13} /> : <Plus size={13} />}
            {showAdd ? "Close" : "New"}
          </button>
        </div>
      </div>

      <p className="text-xs text-muted-foreground">
        Drag a routine onto an empty hour on the calendar, or use Apply to today. Enabled routines also
        auto-apply once on sign-in.
      </p>

      {error && (
        <p className="text-sm text-red-300 bg-red-500/10 border border-red-500/30 rounded-lg px-3 py-2">
          {error}
        </p>
      )}

      {showAdd && (
        <RoutineEditor
          draft={addDraft}
          setDraft={setAddDraft}
          onSave={() => void handleAdd()}
          onCancel={() => setShowAdd(false)}
          saving={saving}
          saveLabel="Save routine"
        />
      )}

      {loading ? (
        <div className="h-24 rounded-lg bg-white/5 animate-pulse" />
      ) : sortedRoutines.length === 0 ? (
        <p className="text-sm text-muted-foreground text-center py-6">
          No routines yet. Click &quot;Add defaults&quot; or &quot;New&quot; to create one.
        </p>
      ) : (
        <div className="space-y-1.5">
          {sortedRoutines.map((r) => (
            <div
              key={r.id}
              draggable={editingId !== r.id}
              onDragStart={(e) => {
                if (editingId === r.id) {
                  e.preventDefault();
                  return;
                }
                const target = e.target as HTMLElement | null;
                if (target?.closest?.("button")) {
                  e.preventDefault();
                  return;
                }
                setRoutineDragData(e.dataTransfer, {
                  title: r.title,
                  category: r.category || "personal",
                  duration_minutes:
                    r.duration_minutes ||
                    minutesBetween(r.start_time || "07:00", r.end_time || "07:30"),
                  color: r.color,
                });
                e.currentTarget.classList.add("opacity-50");
              }}
              onDragEnd={(e) => {
                e.currentTarget.classList.remove("opacity-50");
                clearRoutineDragActive();
              }}
              className={cn(
                "rounded-lg bg-white/[0.03] border border-white/5 px-3 py-2",
                editingId !== r.id && "cursor-grab active:cursor-grabbing",
              )}
              title={editingId === r.id ? undefined : "Drag onto a calendar hour to place"}
            >
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => void toggleEnabled(r)}
                  className={`w-3 h-3 rounded-full shrink-0 ${r.enabled ? "opacity-100" : "opacity-30"}`}
                  style={{ backgroundColor: blockColor(r.category, r.color) }}
                  title={r.enabled ? "Enabled — click to disable" : "Disabled — click to enable"}
                />
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium truncate">{r.title}</div>
                  <div className="text-xs text-muted-foreground tabular-nums">
                    {r.start_time}–{r.end_time || "—"}
                    {r.duration_minutes ? ` · ${r.duration_minutes}m` : ""} · {r.category}
                  </div>
                </div>
                <span className="text-[10px] text-muted-foreground hidden sm:inline">
                  {(r.days || DAY_OPTS).map((d) => d.slice(0, 1).toUpperCase()).join("")}
                </span>
                <button
                  type="button"
                  onClick={() => (editingId === r.id ? (setEditingId(null), setEditDraft(null)) : startEdit(r))}
                  className={cn(
                    "p-1 text-muted-foreground hover:text-sky-300",
                    editingId === r.id && "text-sky-300",
                  )}
                  aria-label="Edit routine"
                >
                  <Pencil size={14} />
                </button>
                <button
                  type="button"
                  onClick={() => void handleDelete(r.id)}
                  className="p-1 text-muted-foreground hover:text-red-400"
                  aria-label="Delete routine"
                >
                  <Trash2 size={14} />
                </button>
              </div>
              {editingId === r.id && editDraft && (
                <RoutineEditor
                  draft={editDraft}
                  setDraft={setEditDraft}
                  onSave={() => void handleSaveEdit()}
                  onCancel={() => {
                    setEditingId(null);
                    setEditDraft(null);
                  }}
                  saving={saving}
                  saveLabel="Save changes"
                />
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
