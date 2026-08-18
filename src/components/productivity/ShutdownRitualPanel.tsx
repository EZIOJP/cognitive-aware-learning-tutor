import { useCallback, useEffect, useMemo, useState } from "react";
import { CheckCircle2, MoonStar } from "lucide-react";
import type { DesktopStats, GoalsStatusResponse } from "../../api/behaviorClient";
import {
  deletePlannerBlock,
  fetchPlannerBlocks,
  rollForwardPlannerBlock,
  type AdherenceSummary,
  type PlannerBlock,
} from "../../api/plannerClient";
import { formatHoursMins } from "../../utils/formatDuration";
import { scoreColor } from "./GlanceBar";
import {
  loadProductivityGoals,
  persistProductivityGoals,
  type ExtraGoal,
} from "./ProductivityGoalsPanel";
import {
  loadLastShutdown,
  saveShutdown,
  shutdownDoneForDay,
  type ShutdownRecord,
} from "./shutdownPrefs";

function startOfDay(d: Date): Date {
  const x = new Date(d);
  x.setHours(0, 0, 0, 0);
  return x;
}

function endOfDay(d: Date): Date {
  const x = new Date(d);
  x.setHours(23, 59, 59, 999);
  return x;
}

function tomorrowNineAm(from: Date): Date {
  const t = new Date(from);
  t.setDate(t.getDate() + 1);
  t.setHours(9, 0, 0, 0);
  return t;
}

function toDayIso(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

type BlockAction = "roll" | "drop" | "keep";

type Props = {
  day: Date;
  desktop: DesktopStats | null;
  adherence: AdherenceSummary | null;
  goalsStatus: GoalsStatusResponse | null;
  onComplete?: () => void;
  refreshKey?: number;
};

export function ShutdownRitualPanel({
  day,
  desktop,
  adherence,
  goalsStatus,
  onComplete,
  refreshKey = 0,
}: Props) {
  const dayIso = toDayIso(day);
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState(0);
  const [blocks, setBlocks] = useState<PlannerBlock[]>([]);
  const [actions, setActions] = useState<Record<number, BlockAction>>({});
  const [reflection, setReflection] = useState("");
  const [extraGoals, setExtraGoals] = useState<ExtraGoal[]>(() => loadProductivityGoals().extraGoals);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(() => shutdownDoneForDay(dayIso));

  const pulse = desktop?.pulse ?? desktop?.avg_productivity_score ?? 0;
  const goal = goalsStatus?.goals?.[0];
  const onPlanH = (adherence?.effective_focus_minutes ?? 0) / 60;

  const incomplete = useMemo(
    () =>
      blocks.filter(
        (b) => b.status !== "done" && b.status !== "cancelled" && b.status !== "rolled",
      ),
    [blocks],
  );

  const loadBlocks = useCallback(async () => {
    try {
      const data = await fetchPlannerBlocks(startOfDay(day), endOfDay(day));
      setBlocks(data);
      const next: Record<number, BlockAction> = {};
      for (const b of data) {
        if (b.status !== "done" && b.status !== "cancelled" && b.status !== "rolled") {
          next[b.id] = "roll";
        }
      }
      setActions(next);
    } catch {
      setBlocks([]);
    }
  }, [day.getTime()]);

  useEffect(() => {
    if (open) void loadBlocks();
  }, [open, loadBlocks, refreshKey]);

  useEffect(() => {
    setDone(shutdownDoneForDay(dayIso));
    const last = loadLastShutdown();
    if (last?.date === dayIso) setReflection(last.reflection || "");
  }, [dayIso, refreshKey]);

  const hour = new Date().getHours();
  const suggestOpen = hour >= 17 && !done;

  const finish = async () => {
    setBusy(true);
    setError(null);
    const carried: string[] = [];
    let dropped = 0;
    try {
      let slot = tomorrowNineAm(day);
      for (const block of incomplete) {
        const act = actions[block.id] ?? "keep";
        if (act === "roll") {
          await rollForwardPlannerBlock(block.id, slot.toISOString());
          carried.push(block.title);
          slot = new Date(slot.getTime() + (block.planned_minutes || 60) * 60_000);
        } else if (act === "drop") {
          await deletePlannerBlock(block.id);
          dropped += 1;
        }
      }
      const record: ShutdownRecord = {
        date: dayIso,
        reflection: reflection.trim(),
        carriedTitles: carried,
        droppedCount: dropped,
        completedAt: new Date().toISOString(),
      };
      saveShutdown(record);
      persistProductivityGoals({ ...loadProductivityGoals(), extraGoals });
      setDone(true);
      setOpen(false);
      setStep(0);
      onComplete?.();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Shutdown failed");
    } finally {
      setBusy(false);
    }
  };

  if (!open && !suggestOpen && !done) return null;

  if (!open) {
    return (
      <div className="rounded-2xl border border-indigo-500/30 bg-indigo-500/10 px-4 py-3 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-sm text-indigo-100">
          <MoonStar size={16} className="text-indigo-300 shrink-0" />
          {done ? (
            <span>Shutdown complete for this day — carried {loadLastShutdown()?.carriedTitles.length ?? 0} to tomorrow.</span>
          ) : (
            <span>End-of-day shutdown — review plan vs actual and carry tasks forward.</span>
          )}
        </div>
        {!done ? (
          <button
            type="button"
            onClick={() => setOpen(true)}
            className="text-xs px-3 py-1.5 rounded-lg bg-indigo-600/80 hover:bg-indigo-600 text-white"
          >
            Start shutdown
          </button>
        ) : null}
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-indigo-500/35 bg-indigo-950/40 p-5 space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold text-sm flex items-center gap-2 text-indigo-100">
            <MoonStar size={16} /> Shutdown ritual
          </h3>
          <p className="text-xs text-muted-foreground mt-1">Step {step + 1} of 4</p>
        </div>
        <button
          type="button"
          className="text-xs text-muted-foreground hover:text-foreground"
          onClick={() => setOpen(false)}
        >
          Close
        </button>
      </div>

      {step === 0 && (
        <div className="grid gap-3 sm:grid-cols-3 text-sm">
          <div className="rounded-xl border border-white/10 bg-black/25 p-3">
            <div className={`text-2xl font-bold tabular-nums ${scoreColor(pulse)}`}>{pulse}</div>
            <div className="text-[10px] uppercase tracking-wider text-muted-foreground mt-1">Pulse</div>
          </div>
          <div className="rounded-xl border border-white/10 bg-black/25 p-3">
            <div className="text-2xl font-bold tabular-nums text-emerald-300">{onPlanH.toFixed(1)}h</div>
            <div className="text-[10px] uppercase tracking-wider text-muted-foreground mt-1">On-plan focus</div>
          </div>
          <div className="rounded-xl border border-white/10 bg-black/25 p-3">
            <div className="text-2xl font-bold tabular-nums text-amber-200">{goal?.pct ?? 0}%</div>
            <div className="text-[10px] uppercase tracking-wider text-muted-foreground mt-1">
              Productive goal
              {goal?.met ? " · met" : ""}
            </div>
          </div>
        </div>
      )}

      {step === 1 && (
        <div className="space-y-2 max-h-56 overflow-y-auto">
          {incomplete.length === 0 ? (
            <p className="text-xs text-muted-foreground">No open blocks — nice closure.</p>
          ) : (
            incomplete.map((b) => (
              <div
                key={b.id}
                className="flex flex-wrap items-center gap-2 rounded-lg border border-white/10 bg-black/20 px-3 py-2 text-xs"
              >
                <span className="font-medium flex-1 min-w-[8rem]">{b.title}</span>
                <span className="text-muted-foreground tabular-nums">
                  {formatHoursMins(b.remaining_minutes || b.planned_minutes)}
                </span>
                <select
                  value={actions[b.id] ?? "roll"}
                  onChange={(e) =>
                    setActions((prev) => ({
                      ...prev,
                      [b.id]: e.target.value as BlockAction,
                    }))
                  }
                  className="rounded-md border border-white/10 bg-black/40 px-2 py-1 text-xs"
                >
                  <option value="roll">Move to tomorrow</option>
                  <option value="keep">Keep today</option>
                  <option value="drop">Drop</option>
                </select>
              </div>
            ))
          )}
        </div>
      )}

      {step === 2 && (
        <div className="space-y-2">
          {extraGoals.filter((g) => g.title.trim()).length === 0 ? (
            <p className="text-xs text-muted-foreground">No extra goals on file.</p>
          ) : (
            extraGoals
              .filter((g) => g.title.trim())
              .map((g) => (
                <label key={g.id} className="flex items-center gap-2 text-xs">
                  <input
                    type="checkbox"
                    checked={g.done}
                    onChange={() =>
                      setExtraGoals((prev) =>
                        prev.map((x) => (x.id === g.id ? { ...x, done: !x.done } : x)),
                      )
                    }
                  />
                  <span className={g.done ? "line-through text-muted-foreground" : ""}>{g.title}</span>
                </label>
              ))
          )}
          <p className="text-[10px] text-muted-foreground">Check off what you finished — saves locally until you update Goals.</p>
        </div>
      )}

      {step === 3 && (
        <label className="block text-xs text-muted-foreground">
          One-line reflection (optional)
          <textarea
            value={reflection}
            onChange={(e) => setReflection(e.target.value)}
            rows={2}
            placeholder="What worked? What to change tomorrow?"
            className="mt-1 w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm text-foreground resize-y"
          />
        </label>
      )}

      {error ? <p className="text-xs text-rose-300">{error}</p> : null}

      <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
        <button
          type="button"
          disabled={step === 0 || busy}
          onClick={() => setStep((s) => Math.max(0, s - 1))}
          className="text-xs px-3 py-1.5 rounded-lg border border-white/10 disabled:opacity-40"
        >
          Back
        </button>
        {step < 3 ? (
          <button
            type="button"
            onClick={() => setStep((s) => s + 1)}
            className="text-xs px-3 py-1.5 rounded-lg bg-indigo-600/80 hover:bg-indigo-600 text-white"
          >
            Next
          </button>
        ) : (
          <button
            type="button"
            disabled={busy}
            onClick={() => void finish()}
            className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg bg-emerald-600/80 hover:bg-emerald-600 text-white disabled:opacity-50"
          >
            <CheckCircle2 size={14} />
            {busy ? "Saving…" : "Complete shutdown"}
          </button>
        )}
      </div>
    </div>
  );
}

export default ShutdownRitualPanel;
