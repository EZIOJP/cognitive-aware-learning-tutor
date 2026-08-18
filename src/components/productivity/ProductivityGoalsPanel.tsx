import { useEffect, useMemo, useState } from "react";
import { Check, ChevronDown, ChevronUp, Gift, Plus, Save, Target, Trash2 } from "lucide-react";
import type { AdherenceSummary } from "../../api/plannerClient";
import {
  fetchProductivityPolicy,
  fetchGoalsStatus,
  saveProductivityPolicy,
  type GoalsStatusResponse,
} from "../../api/behaviorClient";
import { cn } from "../../app/components/ui/utils";

const LS_KEY = "productivity:goals:v1";
export const GOALS_UPDATED_EVENT = "productivity:goals-updated";

export type ExtraGoal = {
  id: string;
  title: string;
  done: boolean;
};

export type ProductivityGoals = {
  focusHoursPerDay: number;
  weeklyFocusHours: number;
  mainGoal: string;
  reward: string;
  extraGoals: ExtraGoal[];
};

const DEFAULT_GOALS: ProductivityGoals = {
  focusHoursPerDay: 4,
  weeklyFocusHours: 24,
  mainGoal: "Complete the Scaler AI/ML course — daily lessons + practice before entertainment.",
  reward: "Unlock games / free time after hitting today's on-plan focus target (off-plan productive apps don't count).",
  extraGoals: [],
};

function newExtraId(): string {
  return `g-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`;
}

function HoursStepper({
  label,
  value,
  min,
  max,
  step,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (n: number) => void;
}) {
  const bump = (dir: 1 | -1) => {
    const next = Math.round((value + dir * step) * 10) / 10;
    onChange(Math.min(max, Math.max(min, next)));
  };

  return (
    <div className="text-xs text-muted-foreground">
      <span className="block mb-1">{label}</span>
      <div className="inline-flex items-stretch rounded-lg border border-white/10 bg-black/30 overflow-hidden h-8">
        <span className="min-w-[2.25rem] px-2 flex items-center justify-center font-mono tabular-nums text-sm text-foreground">
          {value}
        </span>
        <div className="flex flex-col border-l border-white/10 w-6">
          <button
            type="button"
            aria-label={`Increase ${label}`}
            onClick={() => bump(1)}
            className="flex-1 flex items-center justify-center hover:bg-white/10 text-muted-foreground hover:text-foreground"
          >
            <ChevronUp size={12} />
          </button>
          <button
            type="button"
            aria-label={`Decrease ${label}`}
            onClick={() => bump(-1)}
            className="flex-1 flex items-center justify-center border-t border-white/10 hover:bg-white/10 text-muted-foreground hover:text-foreground"
          >
            <ChevronDown size={12} />
          </button>
        </div>
      </div>
    </div>
  );
}

type Props = {
  adherence: AdherenceSummary | null;
  /** Hours already locked by routines / blocks on the selected day */
  lockedHours?: number;
  /** Assumed waking window for capacity hint (default 16h) */
  wakingHours?: number;
  /** Watch sleep score 0–100 for recovery-based capacity hint */
  sleepScore?: number | null;
  onGoalsTextChange?: (text: string) => void;
  /** Fired when the user explicitly Saves — marks the Plan stepper Goals step complete */
  onConfirmed?: () => void;
};

export function focusHoursToGoalMinutes(hours: number): number {
  return Math.min(960, Math.max(15, Math.round(Number(hours) * 60)));
}

export function goalMinutesToFocusHours(mins: number): number {
  return Math.round((Math.max(15, Number(mins) || 240) / 60) * 10) / 10;
}

export function persistProductivityGoals(goals: ProductivityGoals): void {
  localStorage.setItem(LS_KEY, JSON.stringify(goals));
  window.dispatchEvent(new CustomEvent(GOALS_UPDATED_EVENT, { detail: goals }));
}

export function loadProductivityGoals(): ProductivityGoals {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (!raw) return { ...DEFAULT_GOALS };
    const parsed = { ...DEFAULT_GOALS, ...JSON.parse(raw) } as ProductivityGoals;
    if (!Array.isArray(parsed.extraGoals)) parsed.extraGoals = [];
    parsed.extraGoals = parsed.extraGoals
      .filter((g) => g && typeof g.title === "string")
      .map((g) => ({
        id: g.id || newExtraId(),
        title: g.title,
        done: Boolean(g.done),
      }));
    if (
      parsed.mainGoal === "Finish AI/ML and Scaler work before entertainment." ||
      !parsed.mainGoal?.trim()
    ) {
      parsed.mainGoal = DEFAULT_GOALS.mainGoal;
    }
    if (parsed.reward === "Guilt-free break after hitting the focus target.") {
      parsed.reward = DEFAULT_GOALS.reward;
    }
    return parsed;
  } catch {
    return { ...DEFAULT_GOALS };
  }
}

export function formatGoalsForPrompt(goals: ProductivityGoals): string {
  const extras = goals.extraGoals.filter((g) => g.title.trim());
  const extraBlock =
    extras.length === 0
      ? ""
      : ` Extra goals/todos: ${extras
          .map((g) => `${g.done ? "[done] " : ""}${g.title.trim()}`)
          .join("; ")}.`;
  return `${goals.mainGoal} Daily effective-focus target: ${goals.focusHoursPerDay}h. Weekly target: ${goals.weeklyFocusHours}h. Reward: ${goals.reward}.${extraBlock}`;
}

export function ProductivityGoalsPanel({
  adherence,
  lockedHours = 0,
  wakingHours = 16,
  sleepScore = null,
  onGoalsTextChange,
  onConfirmed,
}: Props) {
  const [goals, setGoals] = useState<ProductivityGoals>(() => loadProductivityGoals());
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [draftExtra, setDraftExtra] = useState("");
  const [goalsStatus, setGoalsStatus] = useState<GoalsStatusResponse | null>(null);

  const effectiveHours = (adherence?.effective_focus_minutes ?? 0) / 60;
  const dayPct =
    goals.focusHoursPerDay > 0
      ? Math.min(100, Math.round((effectiveHours / goals.focusHoursPerDay) * 100))
      : 0;
  const remaining = Math.max(0, goals.focusHoursPerDay - effectiveHours);
  const openExtras = goals.extraGoals.filter((g) => !g.done && g.title.trim()).length;
  const freeHours = Math.max(0, wakingHours - lockedHours);
  const focusFit =
    goals.focusHoursPerDay <= 0
      ? "ok"
      : goals.focusHoursPerDay <= freeHours * 0.85
        ? "easy"
        : goals.focusHoursPerDay <= freeHours
          ? "ok"
          : "tight";

  const recoveryFactor =
    sleepScore != null && sleepScore > 0
      ? sleepScore >= 85
        ? 1.0
        : sleepScore >= 70
          ? 0.9
          : sleepScore >= 55
            ? 0.75
            : 0.6
      : null;
  const suggestedFocusHours =
    recoveryFactor != null
      ? Math.round(goals.focusHoursPerDay * recoveryFactor * 10) / 10
      : null;
  const recoveryLabel =
    sleepScore != null && sleepScore > 0
      ? sleepScore >= 85
        ? "Full capacity"
        : sleepScore >= 70
          ? "Good recovery"
          : sleepScore >= 55
            ? "Moderate — trim deep work"
            : "Low recovery — lighter day"
      : null;

  useEffect(() => {
    let cancelled = false;
    void fetchGoalsStatus()
      .then((s) => {
        if (!cancelled) setGoalsStatus(s);
      })
      .catch(() => {
        if (!cancelled) setGoalsStatus(null);
      });
    return () => {
      cancelled = true;
    };
  }, [saved, goals.focusHoursPerDay]);

  const goalsText = useMemo(() => formatGoalsForPrompt(goals), [goals]);

  useEffect(() => {
    onGoalsTextChange?.(goalsText);
  }, [goalsText, onGoalsTextChange]);

  useEffect(() => {
    const onUpdated = () => setGoals(loadProductivityGoals());
    window.addEventListener(GOALS_UPDATED_EVENT, onUpdated);
    return () => window.removeEventListener(GOALS_UPDATED_EVENT, onUpdated);
  }, []);

  useEffect(() => {
    let cancelled = false;
    void fetchProductivityPolicy()
      .then((p) => {
        if (cancelled) return;
        const hours = goalMinutesToFocusHours(p.daily_goal_minutes ?? 240);
        setGoals((prev) =>
          prev.focusHoursPerDay === hours ? prev : { ...prev, focusHoursPerDay: hours },
        );
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  const save = async () => {
    setSaving(true);
    setSaveError(null);
    localStorage.setItem(LS_KEY, JSON.stringify(goals));
    onGoalsTextChange?.(goalsText);
    try {
      await saveProductivityPolicy({
        daily_goal_minutes: focusHoursToGoalMinutes(goals.focusHoursPerDay),
      });
      persistProductivityGoals(goals);
      setSaved(true);
      window.setTimeout(() => setSaved(false), 1800);
      onConfirmed?.();
    } catch (e: unknown) {
      persistProductivityGoals(goals);
      setSaveError(e instanceof Error ? e.message : "Could not update the daily gate goal");
    } finally {
      setSaving(false);
    }
  };

  const addExtra = () => {
    const title = draftExtra.trim();
    if (!title) return;
    setGoals({
      ...goals,
      extraGoals: [...goals.extraGoals, { id: newExtraId(), title, done: false }],
    });
    setDraftExtra("");
  };

  return (
    <div className="rounded-2xl border border-emerald-500/20 bg-emerald-500/[0.04] p-4 space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold text-sm flex items-center gap-2">
            <Target size={15} className="text-emerald-300" />
            Goals & motivation
          </h3>
          <p className="text-xs text-muted-foreground mt-1">
            Routines already locked fixed times. Set focus hours to match free gaps — Save also updates the study gate (unlock / YouTube).
          </p>
          {saveError ? <p className="text-[11px] text-rose-300 mt-1">{saveError}</p> : null}
        </div>
        <button
          type="button"
          onClick={() => void save()}
          disabled={saving}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600/70 hover:bg-emerald-600 text-xs shrink-0 disabled:opacity-50"
        >
          <Save size={12} /> {saving ? "Saving…" : saved ? "Saved" : "Save"}
        </button>
      </div>

      <div
        className={cn(
          "rounded-xl border px-3 py-2.5 text-xs space-y-1",
          focusFit === "tight"
            ? "border-amber-500/40 bg-amber-500/10 text-amber-100"
            : focusFit === "easy"
              ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-100"
              : "border-white/10 bg-black/25 text-muted-foreground",
        )}
      >
        <p className="font-medium text-foreground/90">
          Selected day capacity
        </p>
        <p>
          Locked (routines/blocks): <span className="tabular-nums text-foreground">{lockedHours.toFixed(1)}h</span>
          {" · "}
          Free in ~{wakingHours}h day: <span className="tabular-nums text-foreground">{freeHours.toFixed(1)}h</span>
          {" · "}
          Daily focus: <span className="tabular-nums text-foreground">{goals.focusHoursPerDay}h</span>
        </p>
        <p className="text-[11px] opacity-90">
          {focusFit === "tight"
            ? "Focus target is higher than free time — lower daily hours or free gaps before propose."
            : focusFit === "easy"
              ? "Comfortable fit — propose can fill study blocks up to your focus target."
              : "Tight but workable — propose will pack free gaps near your focus target."}
        </p>
        {recoveryLabel && suggestedFocusHours != null ? (
          <p className="text-[11px] pt-1 border-t border-white/10 mt-2">
            Watch recovery ({sleepScore}): {recoveryLabel}. Suggested focus today:{" "}
            <span className="tabular-nums font-medium text-foreground">{suggestedFocusHours}h</span>
            {" "}(your target {goals.focusHoursPerDay}h).
          </p>
        ) : null}
      </div>

      <div className="space-y-3">
        <label className="block text-xs text-muted-foreground">
          Main goal
          <textarea
            value={goals.mainGoal}
            onChange={(e) => setGoals({ ...goals, mainGoal: e.target.value })}
            rows={3}
            className="mt-1 w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm text-foreground leading-relaxed resize-y min-h-[4.5rem]"
          />
        </label>
        <div className="flex flex-wrap gap-4">
          <HoursStepper
            label="Daily focus h"
            value={goals.focusHoursPerDay}
            min={0.5}
            max={16}
            step={0.5}
            onChange={(n) => setGoals({ ...goals, focusHoursPerDay: n })}
          />
          <HoursStepper
            label="Weekly focus h"
            value={goals.weeklyFocusHours}
            min={1}
            max={80}
            step={1}
            onChange={(n) => setGoals({ ...goals, weeklyFocusHours: n })}
          />
        </div>
      </div>

      <label className="block text-xs text-muted-foreground">
        Reward after target
        <textarea
          value={goals.reward}
          onChange={(e) => setGoals({ ...goals, reward: e.target.value })}
          rows={3}
          className="mt-1 w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm text-foreground leading-relaxed resize-y min-h-[4.5rem]"
        />
      </label>

      {/* Extra goals / todos */}
      <div className="rounded-xl border border-white/10 bg-black/20 p-3 space-y-2">
        <div className="flex items-center justify-between gap-2">
          <p className="text-xs font-medium text-foreground">Extra goals / todos</p>
          {openExtras > 0 && (
            <span className="text-[10px] text-muted-foreground tabular-nums">{openExtras} open</span>
          )}
        </div>
        <ul className="space-y-1.5">
          {goals.extraGoals.length === 0 && (
            <li className="text-[11px] text-muted-foreground py-1">
              Add side goals (e.g. GRE vocab, gym) — they show up in AI propose.
            </li>
          )}
          {goals.extraGoals.map((g) => (
            <li key={g.id} className="flex items-center gap-2 group">
              <button
                type="button"
                onClick={() =>
                  setGoals({
                    ...goals,
                    extraGoals: goals.extraGoals.map((x) =>
                      x.id === g.id ? { ...x, done: !x.done } : x,
                    ),
                  })
                }
                className={cn(
                  "h-5 w-5 rounded border flex items-center justify-center shrink-0",
                  g.done
                    ? "border-emerald-500/60 bg-emerald-500/30 text-emerald-200"
                    : "border-white/20 hover:border-white/40",
                )}
                aria-label={g.done ? "Mark open" : "Mark done"}
              >
                {g.done ? <Check size={12} /> : null}
              </button>
              <input
                value={g.title}
                onChange={(e) =>
                  setGoals({
                    ...goals,
                    extraGoals: goals.extraGoals.map((x) =>
                      x.id === g.id ? { ...x, title: e.target.value } : x,
                    ),
                  })
                }
                className={cn(
                  "flex-1 min-w-0 rounded border border-transparent bg-transparent px-1.5 py-1 text-xs text-foreground focus:border-white/15 focus:bg-black/30",
                  g.done && "line-through text-muted-foreground",
                )}
              />
              <button
                type="button"
                onClick={() =>
                  setGoals({
                    ...goals,
                    extraGoals: goals.extraGoals.filter((x) => x.id !== g.id),
                  })
                }
                className="opacity-0 group-hover:opacity-100 p-1 text-muted-foreground hover:text-rose-300"
                aria-label="Remove goal"
              >
                <Trash2 size={12} />
              </button>
            </li>
          ))}
        </ul>
        <div className="flex gap-2 pt-1">
          <input
            value={draftExtra}
            onChange={(e) => setDraftExtra(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                addExtra();
              }
            }}
            placeholder="Add a goal or todo…"
            className="flex-1 rounded border border-white/10 bg-black/30 px-2 py-1.5 text-xs text-foreground"
          />
          <button
            type="button"
            onClick={addExtra}
            disabled={!draftExtra.trim()}
            className="inline-flex items-center gap-1 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-1.5 text-xs text-emerald-200 hover:bg-emerald-500/20 disabled:opacity-40"
          >
            <Plus size={12} /> Add
          </button>
        </div>
      </div>

      {goalsStatus && (goalsStatus.alerts.length > 0 || goalsStatus.goals.length > 0) ? (
        <div className="rounded-xl border border-white/10 bg-black/20 p-3 space-y-2 text-xs">
          <p className="font-medium text-foreground/90">Today&apos;s alerts & goal</p>
          {goalsStatus.goals.map((g) => (
            <p key={g.id} className="text-muted-foreground">
              {g.label}: {Math.round(g.current_seconds / 60)} / {Math.round(g.target_seconds / 60)} min
              {g.met ? " · met" : ` · ${g.pct}%`}
            </p>
          ))}
          {goalsStatus.alerts.map((a) => (
            <p
              key={a.id}
              className={a.triggered ? "text-amber-200" : "text-muted-foreground"}
            >
              {a.label}: {Math.round(a.current_seconds / 60)} / {Math.round(a.max_seconds / 60)} min
              {a.fired ? " · notified" : a.triggered ? " · triggered" : ""}
            </p>
          ))}
        </div>
      ) : null}

      <div
        className={cn(
          "rounded-lg border p-3 transition-colors",
          remaining <= 0
            ? "border-amber-500/40 bg-amber-500/10"
            : "border-white/10 bg-black/20",
        )}
      >
        <div className="flex items-center justify-between text-xs">
          <span className="text-muted-foreground">Selected day effective focus</span>
          <span
            className={cn(
              "tabular-nums",
              remaining <= 0 ? "text-amber-200" : "text-emerald-200",
            )}
          >
            {effectiveHours.toFixed(1)}h / {goals.focusHoursPerDay}h
          </span>
        </div>
        <div className="mt-2 h-2 rounded-full bg-white/10 overflow-hidden">
          <div
            className={cn("h-full rounded-full", remaining <= 0 ? "bg-amber-400" : "bg-emerald-400")}
            style={{ width: `${dayPct}%` }}
          />
        </div>
        {remaining <= 0 ? (
          <div className="mt-3 flex items-start gap-2 rounded-md border border-amber-500/30 bg-amber-500/10 px-2.5 py-2">
            <Gift size={16} className="mt-0.5 shrink-0 text-amber-300" aria-hidden />
            <div className="min-w-0">
              <p className="text-xs font-semibold text-amber-100">Reward unlocked</p>
              <p className="text-[11px] text-amber-100/80 mt-0.5 leading-snug">{goals.reward}</p>
            </div>
          </div>
        ) : (
          <p className="text-[11px] text-muted-foreground mt-2">
            {remaining.toFixed(1)}h effective focus left before entertainment.
          </p>
        )}
      </div>
    </div>
  );
}

export default ProductivityGoalsPanel;
