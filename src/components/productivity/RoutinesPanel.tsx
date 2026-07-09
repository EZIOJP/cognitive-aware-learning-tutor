import { useCallback, useEffect, useState } from "react";
import { Coffee, Loader2, Plus, RefreshCw, Sparkles, Trash2 } from "lucide-react";
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

const DAY_OPTS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"];

export function RoutinesPanel({ onApplied }: { onApplied?: () => void }) {
  const [routines, setRoutines] = useState<PlannerRoutine[]>([]);
  const [loading, setLoading] = useState(true);
  const [applying, setApplying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showAdd, setShowAdd] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newStart, setNewStart] = useState("07:00");
  const [newEnd, setNewEnd] = useState("07:30");
  const [newCategory, setNewCategory] = useState("personal");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setRoutines(await fetchRoutines());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load routines");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const handleSeed = async () => {
    setError(null);
    try {
      const rows = await seedDefaultRoutines();
      setRoutines(rows);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Seed failed");
    }
  };

  const handleApply = async () => {
    setApplying(true);
    setError(null);
    try {
      const r = await applyRoutines();
      onApplied?.();
      alert(`Added ${r.created} routine block(s) to today's planner.`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Apply failed");
    } finally {
      setApplying(false);
    }
  };

  const handleAdd = async () => {
    if (!newTitle.trim()) return;
    try {
      await createRoutine({
        title: newTitle.trim(),
        category: newCategory,
        start_time: newStart,
        end_time: newEnd,
      });
      setNewTitle("");
      setShowAdd(false);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Create failed");
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
            onClick={() => setShowAdd((v) => !v)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-violet-600/80 hover:bg-violet-600 text-xs"
          >
            <Plus size={13} />
            New
          </button>
        </div>
      </div>

      <p className="text-xs text-muted-foreground">
        Persistent blocks like Bible, meals, and bath — set once, apply each day without re-importing.
        Enabled routines auto-apply once when you sign in (missing slots only).
      </p>

      {error && (
        <p className="text-sm text-red-300 bg-red-500/10 border border-red-500/30 rounded-lg px-3 py-2">
          {error}
        </p>
      )}

      {showAdd && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-2 p-3 rounded-lg border border-white/10 bg-black/20">
          <input
            className="col-span-2 md:col-span-2 text-sm bg-black/30 border border-white/10 rounded px-2 py-1"
            placeholder="Title (e.g. Bible)"
            value={newTitle}
            onChange={(e) => setNewTitle(e.target.value)}
          />
          <input
            type="time"
            className="text-sm bg-black/30 border border-white/10 rounded px-2 py-1"
            value={newStart}
            onChange={(e) => setNewStart(e.target.value)}
          />
          <input
            type="time"
            className="text-sm bg-black/30 border border-white/10 rounded px-2 py-1"
            value={newEnd}
            onChange={(e) => setNewEnd(e.target.value)}
          />
          <select
            className="text-sm bg-black/30 border border-white/10 rounded px-2 py-1"
            value={newCategory}
            onChange={(e) => setNewCategory(e.target.value)}
          >
            <option value="spiritual">spiritual</option>
            <option value="food">food</option>
            <option value="personal">personal</option>
            <option value="break">break</option>
            <option value="study">study</option>
          </select>
          <button
            type="button"
            onClick={() => void handleAdd()}
            className="col-span-2 md:col-span-5 text-xs py-1.5 rounded bg-emerald-600/80 hover:bg-emerald-600"
          >
            Save routine
          </button>
        </div>
      )}

      {loading ? (
        <div className="h-24 rounded-lg bg-white/5 animate-pulse" />
      ) : routines.length === 0 ? (
        <p className="text-sm text-muted-foreground text-center py-6">
          No routines yet. Click &quot;Add defaults&quot; for Bible, meals, and bath templates.
        </p>
      ) : (
        <div className="space-y-1.5">
          {routines.map((r) => (
            <div
              key={r.id}
              className="flex items-center gap-3 py-2 px-3 rounded-lg bg-white/[0.03] border border-white/5"
            >
              <button
                type="button"
                onClick={() => void toggleEnabled(r)}
                className={`w-3 h-3 rounded-full shrink-0 ${r.enabled ? "opacity-100" : "opacity-30"}`}
                style={{ backgroundColor: blockColor(r.category, r.color) }}
                title={r.enabled ? "Enabled" : "Disabled"}
              />
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium truncate">{r.title}</div>
                <div className="text-xs text-muted-foreground tabular-nums">
                  {r.start_time}–{r.end_time || "—"} · {r.category}
                </div>
              </div>
              <span className="text-[10px] text-muted-foreground hidden sm:inline">
                {(r.days || DAY_OPTS).map((d) => d.slice(0, 1).toUpperCase()).join("")}
              </span>
              <button
                type="button"
                onClick={() => void handleDelete(r.id)}
                className="p-1 text-muted-foreground hover:text-red-400"
                aria-label="Delete routine"
              >
                <Trash2 size={14} />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
