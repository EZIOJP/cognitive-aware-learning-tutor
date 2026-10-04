import { useCallback, useEffect, useState } from "react";
import { Check, Loader2, Moon, Plus, Trash2 } from "lucide-react";
import {
  deleteDayTask,
  evaluateDayClose,
  fetchDayLoopSnapshot,
  setDayTaskDone,
  todayYmd,
  upsertDayTask,
  type DayLoopSnapshot,
  type DayLoopTask,
} from "../../api/dayLoopClient";
import { isFocusEnforcerBridgeAvailable } from "../../lib/enforcerNativeCmd";
import { subscribeFocusStatus } from "../../lib/focusStatusBus";
import { isFocusDesktopShell } from "../../utils/focusDesktopShell";
import { focusDataUrl } from "../../utils/focusDataUrl";
import { MORNING_UPDATED_EVENT } from "./ConfirmPlanButton";

/** Focus landing strip: tasks + SoftLand mode + dual-gate / close-out prompts. */
export default function DayLoopLanding() {
  const focus = isFocusDesktopShell();
  const [loop, setLoop] = useState<DayLoopSnapshot | null>(null);
  const [loading, setLoading] = useState(false);
  const [hint, setHint] = useState<string | null>(null);
  const [newTitle, setNewTitle] = useState("");
  const [modeLabel, setModeLabel] = useState<string>("—");

  const refresh = useCallback(async () => {
    if (!focus || !isFocusEnforcerBridgeAvailable()) return;
    setLoading(true);
    try {
      const snap = await fetchDayLoopSnapshot();
      setLoop(snap);
      try {
        const st = await fetch(focusDataUrl("softland_policy.json"), { cache: "no-store" });
        if (st.ok) {
          const j = (await st.json()) as {
            softland_enabled?: boolean;
            runtime?: { free_until?: string | null; bedtime_active?: boolean };
          };
          if (j.runtime?.bedtime_active) setModeLabel("BEDTIME");
          else if (j.runtime?.free_until) setModeLabel("FREE");
          else if (j.softland_enabled) setModeLabel("STUDY");
          else setModeLabel("OFF");
        }
      } catch {
        /* ignore */
      }
    } finally {
      setLoading(false);
    }
  }, [focus]);

  // Prefer shared status bus — do not pipe day.loop_snapshot on an interval (UI lag).
  useEffect(() => {
    if (!focus) return;
    const unsub = subscribeFocusStatus((snap) => {
      if (snap.dayLoop) setLoop(snap.dayLoop);
      const j = snap.softland;
      if (j) {
        if (j.runtime?.bedtime_active) setModeLabel("BEDTIME");
        else if (j.runtime?.free_until) setModeLabel("FREE");
        else if (j.softland_enabled) setModeLabel("STUDY");
        else setModeLabel("OFF");
      }
      setLoading(false);
    });
    const onMorning = () => void refresh();
    window.addEventListener(MORNING_UPDATED_EVENT, onMorning);
    return () => {
      unsub();
      window.removeEventListener(MORNING_UPDATED_EVENT, onMorning);
    };
  }, [focus, refresh]);

  if (!focus) return null;

  async function toggleTask(t: DayLoopTask) {
    await setDayTaskDone(t.id, !t.done);
    await refresh();
    await evaluateDayClose();
    await refresh();
  }

  async function addTask() {
    const title = newTitle.trim();
    if (!title) return;
    await upsertDayTask({ title, done: false });
    setNewTitle("");
    await refresh();
  }

  async function removeTask(id: number) {
    await deleteDayTask(id);
    await refresh();
  }

  async function onEvaluate() {
    const r = await evaluateDayClose();
    if (r.granted) setHint(`1h free granted until ${r.free_until || "soon"}`);
    else setHint("Dual gate not met yet (checkboxes + ≥50% planned time).");
    await refresh();
  }

  const tasks = loop?.tasks || [];

  return (
    <section className="gloss-panel rounded-xl p-4 space-y-3 border border-white/10">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-xs font-semibold text-sky-100">Today</p>
          <p className="text-[11px] text-muted-foreground">
            Mode <span className="font-mono text-foreground/90">{modeLabel}</span>
            {loop ? (
              <>
                {" "}
                · planned {loop.planned_minutes}m · tracked {loop.tracked_productive_minutes}m
                (need {loop.threshold_minutes}m) · tasks {loop.tasks_done}/{loop.tasks_total}
              </>
            ) : null}
          </p>
        </div>
        {loading ? <Loader2 className="size-4 animate-spin text-muted-foreground" /> : null}
      </div>

      {loop?.closeout_free_granted || loop?.free_until ? (
        <p className="text-[11px] rounded-md border border-emerald-500/30 bg-emerald-500/10 px-2 py-1.5 text-emerald-100">
          Free window active{loop.free_until ? ` until ${loop.free_until}` : ""} — controlled
          entertainment.
        </p>
      ) : null}

      <ul className="space-y-1.5">
        {tasks.map((t) => (
          <li
            key={t.id}
            className="flex items-center gap-2 rounded-lg border border-white/10 bg-black/20 px-2 py-1.5"
          >
            <button
              type="button"
              className="size-6 rounded border border-white/20 flex items-center justify-center shrink-0"
              onClick={() => void toggleTask(t)}
              aria-label={t.done ? "Mark incomplete" : "Mark done"}
            >
              {t.done ? <Check className="size-3.5 text-emerald-300" /> : null}
            </button>
            <span
              className={`flex-1 text-sm ${t.done ? "line-through text-muted-foreground" : "text-foreground/90"}`}
            >
              {t.title}
            </span>
            <button
              type="button"
              className="text-muted-foreground hover:text-rose-300"
              onClick={() => void removeTask(t.id)}
              aria-label="Delete task"
            >
              <Trash2 className="size-3.5" />
            </button>
          </li>
        ))}
        {!tasks.length ? (
          <li className="text-[11px] text-muted-foreground">Add goal tasks for today (checkbox gate).</li>
        ) : null}
      </ul>

      <div className="flex gap-2">
        <input
          className="flex-1 rounded-lg border border-white/10 bg-black/30 px-2 py-1.5 text-sm"
          placeholder="New goal task…"
          value={newTitle}
          onChange={(e) => setNewTitle(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") void addTask();
          }}
        />
        <button
          type="button"
          className="rounded-lg border border-white/15 px-2 py-1.5 text-xs hover:bg-white/5"
          onClick={() => void addTask()}
        >
          <Plus className="size-4" />
        </button>
      </div>

      <div className="flex flex-wrap gap-2 pt-1">
        <button
          type="button"
          className="rounded-lg bg-amber-400/90 px-2.5 py-1.5 text-[11px] font-semibold text-amber-950"
          onClick={() => void onEvaluate()}
        >
          Check free unlock
        </button>
        <span className="inline-flex items-center gap-1 text-[10px] text-muted-foreground">
          <Moon className="size-3" /> {todayYmd()} · no carry-forward
        </span>
      </div>
      {hint ? <p className="text-[11px] text-sky-200/90">{hint}</p> : null}
    </section>
  );
}
