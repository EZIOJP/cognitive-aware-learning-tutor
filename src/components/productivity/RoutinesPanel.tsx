import { useCallback, useEffect, useState } from "react";
import {
  ChevronDown,
  ChevronUp,
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
  clearPlannerDay,
  createRoutine,
  deleteRoutine,
  fetchRoutines,
  seedDefaultRoutines,
  updateRoutine,
  type PlannerRoutine,
} from "../../api/plannerClient";
import { cn } from "../../app/components/ui/utils";
import { setRoutineDragData, clearRoutineDragActive } from "./routineDrag";
import DayRhythmPanel from "./DayRhythmPanel";

const DAY_OPTS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"] as const;
const DAY_LABELS = ["M", "T", "W", "T", "F", "S", "S"] as const;
const CATEGORIES = ["spiritual", "food", "personal", "break", "study"] as const;

/** Compact list duration — avoids "0 hours 30 mins" wall of text. */
function formatCompactMins(mins: number | null | undefined): string {
  if (mins == null || Number.isNaN(Number(mins))) return "";
  const n = Math.max(0, Math.round(Number(mins)));
  if (n < 60) return `${n}m`;
  const h = Math.floor(n / 60);
  const m = n % 60;
  return m ? `${h}h ${m}m` : `${h}h`;
}

function DayMask({ days }: { days: string[] }) {
  const active = days?.length ? days : [...DAY_OPTS];
  const all = DAY_OPTS.every((d) => active.includes(d));
  if (all) return null;
  return (
    <span
      className="inline-flex gap-px font-mono text-[10px] tracking-wide select-none text-muted-foreground/70"
      title={active.join(", ")}
      aria-label={`Days: ${active.join(", ")}`}
    >
      {DAY_OPTS.map((d, i) => {
        const on = active.includes(d);
        return (
          <span key={d} className={on ? "text-muted-foreground/85" : "text-muted-foreground/20"}>
            {DAY_LABELS[i]}
          </span>
        );
      })}
    </span>
  );
}

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
                ? "bg-emerald-500/25 text-emerald-100 border border-emerald-400/35"
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
  const [clearing, setClearing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
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

  const todayYmd = () => {
    const t = new Date();
    const y = t.getFullYear();
    const m = String(t.getMonth() + 1).padStart(2, "0");
    const d = String(t.getDate()).padStart(2, "0");
    return `${y}-${m}-${d}`;
  };

  const busy = applying || clearing;

  const formatRoutineErr = (raw: unknown): string => {
    const msg = raw instanceof Error ? raw.message : String(raw || "Failed");
    if (msg === "free_day_required" || /free.?day/i.test(msg)) {
      return "Today's plan is already set. Apply routines while planning a new day, or on a free day.";
    }
    if (msg === "enforcer_unreachable") {
      return "Enforcer unreachable — open calt_focus (pipe) to add or remove routines.";
    }
    if (msg === "not_found") return "Routine already removed.";
    return msg;
  };

  const handleApply = async () => {
    setApplying(true);
    setError(null);
    setStatus(null);
    try {
      await applyRoutines(todayYmd());
      onApplied?.();
      setStatus("Applied routines for today.");
    } catch (e) {
      setError(formatRoutineErr(e));
    } finally {
      setApplying(false);
    }
  };

  const handleClearToday = async () => {
    if (
      !confirm(
        "Delete all plan blocks for today? Routines stay — only today's calendar blocks are removed.",
      )
    ) {
      return;
    }
    setClearing(true);
    setError(null);
    setStatus(null);
    try {
      await clearPlannerDay(todayYmd());
      onApplied?.();
      setStatus("Cleared today's plan blocks.");
    } catch (e) {
      setError(formatRoutineErr(e));
    } finally {
      setClearing(false);
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
      onApplied?.();
    } catch (e) {
      setError(formatRoutineErr(e));
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
      setError(formatRoutineErr(e));
    } finally {
      setSaving(false);
    }
  };

  const toggleEnabled = async (r: PlannerRoutine) => {
    try {
      await updateRoutine(r.id, { enabled: !r.enabled });
      await load();
    } catch (e) {
      setError(formatRoutineErr(e));
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm("Remove this routine and today's matching calendar blocks?")) return;
    setError(null);
    setStatus(null);
    const prev = routines;
    // Optimistic — mirror used to lag up to 60s and made delete look like a no-op.
    const next = routines.filter((r) => r.id !== id);
    setRoutines(next);
    onRoutinesChange?.(next);
    if (editingId === id) {
      setEditingId(null);
      setEditDraft(null);
    }
    try {
      const res = await deleteRoutine(id);
      onApplied?.();
      const cleared = res.blocks_cleared || 0;
      setStatus(
        cleared > 0
          ? `Removed routine and ${cleared} calendar block${cleared === 1 ? "" : "s"} today.`
          : "Removed routine.",
      );
      await load();
    } catch (e) {
      setRoutines(prev);
      onRoutinesChange?.(prev);
      setError(formatRoutineErr(e));
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-end gap-1.5">
          <button
            type="button"
            disabled={busy}
            onClick={() => void handleApply()}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-amber-600/85 hover:bg-amber-600 text-xs font-medium text-white disabled:opacity-50"
          >
            {applying ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
            Apply to today
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() => void handleClearToday()}
            className="flex items-center gap-1 px-2 py-1.5 rounded-lg text-xs text-muted-foreground hover:text-rose-200 hover:bg-rose-500/10 border border-transparent hover:border-rose-500/20 disabled:opacity-50"
            title="Remove all plan blocks for today"
          >
            {clearing ? <Loader2 size={12} className="animate-spin" /> : <Trash2 size={12} />}
            Clear
          </button>
          {routines.length === 0 && (
            <button
              type="button"
              onClick={() => void handleSeed()}
              className="flex items-center gap-1 px-2 py-1.5 rounded-lg text-xs text-muted-foreground hover:text-foreground hover:bg-white/5"
            >
              <Sparkles size={12} />
              Defaults
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
            className={cn(
              "flex items-center gap-1 px-2 py-1.5 rounded-lg text-xs border border-white/10",
              showAdd
                ? "bg-white/10 text-foreground"
                : "bg-transparent text-muted-foreground hover:text-foreground hover:bg-white/[0.06]",
            )}
          >
            {showAdd ? <X size={12} /> : <Plus size={12} />}
            {showAdd ? "Close" : "New"}
          </button>
      </div>

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
          No routines yet. Click &quot;Defaults&quot; or &quot;New&quot; to create one.
        </p>
      ) : (
        <ul className="divide-y divide-white/[0.05] rounded-lg border border-white/[0.06] overflow-hidden">
          {sortedRoutines.map((r) => {
            const dur =
              r.duration_minutes ||
              minutesBetween(r.start_time || "07:00", r.end_time || "07:30");
            const compact = formatCompactMins(dur);
            return (
              <li
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
                    duration_minutes: dur,
                    color: r.color,
                  });
                  e.currentTarget.classList.add("opacity-50");
                }}
                onDragEnd={(e) => {
                  e.currentTarget.classList.remove("opacity-50");
                  clearRoutineDragActive();
                }}
                className={cn(
                  "px-2.5 py-2 bg-transparent hover:bg-white/[0.025] transition-colors",
                  editingId !== r.id && "cursor-grab active:cursor-grabbing",
                  editingId === r.id && "bg-white/[0.03]",
                )}
                title={editingId === r.id ? undefined : "Drag onto a calendar hour to place"}
              >
                <div className="flex items-center gap-2.5 min-h-[2.25rem]">
                  <button
                    type="button"
                    onClick={() => void toggleEnabled(r)}
                    className={`w-2.5 h-2.5 rounded-full shrink-0 ${r.enabled ? "opacity-100" : "opacity-30"}`}
                    style={{ backgroundColor: blockColor(r.category, r.color) }}
                    title={r.enabled ? "Enabled — click to disable" : "Disabled — click to enable"}
                  />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-baseline gap-2 min-w-0">
                      <span className="text-sm font-medium text-foreground truncate">{r.title}</span>
                      <span className="text-[11px] text-muted-foreground/90 tabular-nums shrink-0">
                        {r.start_time}–{r.end_time || "—"}
                        {compact ? ` · ${compact}` : ""}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 mt-0.5">
                      <span className="text-[10px] text-muted-foreground/60 capitalize truncate">
                        {r.category}
                      </span>
                      <span className="hidden sm:inline-flex ml-auto pl-2">
                        <DayMask days={r.days || [...DAY_OPTS]} />
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-0.5 shrink-0 opacity-55 hover:opacity-100 transition-opacity">
                    <button
                      type="button"
                      onClick={() =>
                        editingId === r.id
                          ? (setEditingId(null), setEditDraft(null))
                          : startEdit(r)
                      }
                      className={cn(
                        "p-1 rounded text-muted-foreground hover:text-sky-300 hover:bg-white/5",
                        editingId === r.id && "text-sky-300 opacity-100",
                      )}
                      aria-label="Edit routine"
                    >
                      <Pencil size={13} />
                    </button>
                    <button
                      type="button"
                      onClick={() => void handleDelete(r.id)}
                      className="p-1 rounded text-muted-foreground hover:text-red-400 hover:bg-white/5"
                      aria-label="Delete routine"
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
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
              </li>
            );
          })}
        </ul>
      )}

      {status && (
        <p className="text-[11px] text-emerald-200/90" role="status">
          {status}
        </p>
      )}

      <DayRhythmPanel />
    </div>
  );
}
