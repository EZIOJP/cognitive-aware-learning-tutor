import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router";
import { CheckCircle2, Clock, ListTodo, Sparkles } from "lucide-react";
import { fetchPlannerBlocks, type PlannerBlock } from "../../api/plannerClient";
import {
  confirmMorningPlan,
  draftMorningAutoPlan,
  fetchDistractionGate,
  fetchProductivityPolicy,
  type BrowserGateSection,
  type MorningGate,
} from "../../api/behaviorClient";
import {
  browserModeHint,
  formatBlockClock,
  planConfirmUi,
} from "./morningPlanUi";
import {
  formatGoalsForPrompt,
  GOALS_UPDATED_EVENT,
  loadProductivityGoals,
} from "./ProductivityGoalsPanel";
import {
  carriedTitlesForMorning,
  formatShutdownDayLabel,
  loadLastShutdown,
  SHUTDOWN_UPDATED_EVENT,
} from "./shutdownPrefs";
import { checkPlanOvercommit } from "./planCapacityUtils";
import { loadProductivityGoals } from "./ProductivityGoalsPanel";

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

function currentGoalsText(): string {
  try {
    return formatGoalsForPrompt(loadProductivityGoals()).trim();
  } catch {
    return "";
  }
}

type Props = {
  day?: Date;
  refreshKey?: number;
  onPlannerChange?: () => void;
};

/**
 * Morning Plan sections — Auto plan · Today’s blocks · Confirm · mode hint.
 * Plan tab only (not Calendar overview).
 */
export function MorningAutoPlanPanel({
  day: dayProp,
  refreshKey = 0,
  onPlannerChange,
}: Props) {
  const day = dayProp ?? new Date();
  const [blocks, setBlocks] = useState<PlannerBlock[]>([]);
  const [morning, setMorning] = useState<MorningGate | null>(null);
  const [browser, setBrowser] = useState<BrowserGateSection | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [confirmError, setConfirmError] = useState<string | null>(null);
  const [drafting, setDrafting] = useState(false);
  const [draftError, setDraftError] = useState<string | null>(null);
  const [goalsText, setGoalsText] = useState(() => currentGoalsText());
  const [dailyGoalMinutes, setDailyGoalMinutes] = useState(240);
  const [overcommitAck, setOvercommitAck] = useState(false);
  const isToday = startOfDay(day).getTime() === startOfDay(new Date()).getTime();

  const loadBlocks = useCallback(async () => {
    if (!isToday) return;
    try {
      const data = await fetchPlannerBlocks(startOfDay(day), endOfDay(day));
      setBlocks(data);
    } catch {
      setBlocks([]);
    }
  }, [day.getTime(), isToday]);

  useEffect(() => {
    void loadBlocks();
  }, [loadBlocks, refreshKey]);

  useEffect(() => {
    setGoalsText(currentGoalsText());
  }, [refreshKey, isToday]);

  useEffect(() => {
    void fetchProductivityPolicy()
      .then((p) => setDailyGoalMinutes(p.daily_goal_minutes ?? 240))
      .catch(() => setDailyGoalMinutes(240));
  }, [refreshKey]);

  useEffect(() => {
    const onGoals = () => setGoalsText(currentGoalsText());
    window.addEventListener(GOALS_UPDATED_EVENT, onGoals);
    return () => window.removeEventListener(GOALS_UPDATED_EVENT, onGoals);
  }, []);

  useEffect(() => {
    if (!isToday) return;
    let cancelled = false;
    fetchDistractionGate()
      .then((g) => {
        if (cancelled) return;
        setMorning(g.morning ?? null);
        setBrowser(g.browser ?? null);
      })
      .catch(() => {
        if (!cancelled) {
          setMorning(null);
          setBrowser(null);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [isToday, refreshKey, blocks.length]);

  const todayBlocks = useMemo(
    () =>
      blocks
        .filter((b) => {
          const start = new Date(b.start_at);
          return start >= startOfDay(day) && start <= endOfDay(day) && b.status !== "rolled";
        })
        .sort((a, b) => new Date(a.start_at).getTime() - new Date(b.start_at).getTime()),
    [blocks, day.getTime()],
  );

  const goalsOk = goalsText.trim().length >= 3;

  const overcommit = useMemo(
    () =>
      checkPlanOvercommit({
        blocks: todayBlocks,
        dailyGoalMinutes,
        suggestedFocusHours: loadProductivityGoals().focusHoursPerDay,
      }),
    [todayBlocks, dailyGoalMinutes],
  );

  const confirmPlan = async () => {
    setConfirming(true);
    setConfirmError(null);
    const goals = currentGoalsText();
    setGoalsText(goals);
    if (goals.trim().length < 3) {
      setConfirmError("Goals required");
      setConfirming(false);
      return;
    }
    if (overcommit.level === "over" && !overcommitAck) {
      setConfirmError(overcommit.message);
      setConfirming(false);
      return;
    }
    try {
      const r = await confirmMorningPlan({ goals });
      setMorning(r.morning ?? null);
      onPlannerChange?.();
    } catch (e: unknown) {
      setConfirmError(e instanceof Error ? e.message : "Confirm failed");
    } finally {
      setConfirming(false);
    }
  };

  const draftAutoPlan = async (opts?: { addMore?: boolean }) => {
    setDrafting(true);
    setDraftError(null);
    try {
      const r = await draftMorningAutoPlan({ addMore: opts?.addMore });
      setMorning(r.morning ?? null);
      await loadBlocks();
      onPlannerChange?.();
    } catch (e: unknown) {
      setDraftError(e instanceof Error ? e.message : "Draft failed");
    } finally {
      setDrafting(false);
    }
  };

  const autoPlanTitles = useMemo(() => {
    const fromGate = (morning?.auto_plan?.titles || []).filter(Boolean);
    if (fromGate.length > 0) return fromGate;
    return todayBlocks.map((b) => b.title).filter(Boolean);
  }, [morning?.auto_plan?.titles, todayBlocks]);

  const planExists = morning?.auto_plan?.reason === "plan_exists";

  const [carriedFromShutdown, setCarriedFromShutdown] = useState<string[]>(() =>
    carriedTitlesForMorning(),
  );
  useEffect(() => {
    const refresh = () => setCarriedFromShutdown(carriedTitlesForMorning());
    refresh();
    window.addEventListener(SHUTDOWN_UPDATED_EVENT, refresh);
    return () => window.removeEventListener(SHUTDOWN_UPDATED_EVENT, refresh);
  }, [refreshKey]);

  const lastShutdown = loadLastShutdown();

  const mode = useMemo(
    () =>
      browserModeHint({
        mode: browser?.mode,
        modeLabel: browser?.mode_label,
        freeAfter: browser?.free_after,
        note: browser?.note,
      }),
    [browser?.mode, browser?.mode_label, browser?.free_after, browser?.note],
  );

  const confirm = useMemo(
    () =>
      planConfirmUi({
        next: morning?.next,
        planDone: morning?.plan_done,
        phase: morning?.plan_window?.phase,
        confirmAvailable: morning?.plan_window?.confirm_available,
        startClock: morning?.plan_window?.start_clock,
        endLabel: morning?.plan_window?.end_label,
        eodHhmm: morning?.plan_window?.eod_hhmm,
        blocksToday: morning?.blocks_today ?? todayBlocks.length,
        planPoints: morning?.rewards?.plan_points,
        serverHint: morning?.hint,
      }),
    [morning, todayBlocks.length],
  );

  if (!isToday) {
    return (
      <p className="text-[11px] text-muted-foreground px-1">
        Switch the schedule to <strong className="text-foreground">today</strong> for auto plan and
        morning confirm.
      </p>
    );
  }

  if (!morning?.enabled && !mode) return null;

  const showAuto = Boolean(morning?.enabled && morning.bible_done);
  // Show confirm whenever Bible is done (or already confirmed) — not only morning.next=plan.
  const showConfirm = Boolean(
    morning?.enabled && (morning.bible_done || morning.plan_done || morning.next === "plan"),
  );

  return (
    <div className="space-y-3">
      {carriedFromShutdown.length > 0 && lastShutdown ? (
        <div className="rounded-xl border border-indigo-500/30 bg-indigo-500/10 px-3 py-2 text-[11px] text-indigo-100">
          <p className="font-medium">Carried from {formatShutdownDayLabel(lastShutdown.date)} shutdown</p>
          <ul className="mt-1 list-disc list-inside text-muted-foreground">
            {carriedFromShutdown.map((t) => (
              <li key={t}>{t}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {mode && (
        <div
          className={`rounded-xl border px-3 py-2 text-[11px] ${
            mode.tone === "strict"
              ? "border-amber-500/30 bg-amber-500/10 text-amber-50/90"
              : "border-teal-500/25 bg-teal-500/10 text-teal-50/90"
          }`}
        >
          <span
            className={`inline-flex rounded px-1.5 py-0.5 mr-2 font-semibold tracking-wide ${
              mode.tone === "strict"
                ? "bg-amber-500/25 text-amber-100 border border-amber-400/30"
                : "bg-teal-500/20 text-teal-100 border border-teal-400/25"
            }`}
          >
            Browser: {mode.label}
          </span>
          <span className="text-muted-foreground">{mode.detail}</span>
        </div>
      )}

      {morning?.enabled && !morning.bible_done && (
        <p className="text-[11px] text-amber-200/85 px-0.5">
          Finish today’s Bible chapter first — then auto plan and confirm unlock here.
        </p>
      )}

      {showAuto && (
        <section
          aria-labelledby="plan-auto-heading"
          className="rounded-xl border border-sky-500/35 bg-sky-500/10 p-3 space-y-2"
        >
          <h3
            id="plan-auto-heading"
            className="text-sm font-medium text-sky-100 flex items-center gap-2"
          >
            <Sparkles size={14} className="text-sky-300 shrink-0" />
            Auto plan
          </h3>
          {planExists ? (
            <>
              <p className="text-[11px] text-sky-100/80">
                Blocks already on today — add more, or confirm as-is?
              </p>
              {autoPlanTitles.length > 0 && (
                <ul className="text-xs text-sky-50/90 space-y-1 list-disc list-inside">
                  {autoPlanTitles.slice(0, 6).map((t) => (
                    <li key={t}>{t}</li>
                  ))}
                  {autoPlanTitles.length > 6 && (
                    <li className="list-none text-sky-100/60">+{autoPlanTitles.length - 6} more</li>
                  )}
                </ul>
              )}
              {draftError && <p className="text-[11px] text-rose-300">{draftError}</p>}
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  disabled={drafting}
                  onClick={() => void draftAutoPlan({ addMore: true })}
                  className="text-xs px-3 py-1.5 rounded-md bg-sky-500/25 text-sky-50 border border-sky-400/40 hover:bg-sky-500/35 disabled:opacity-50"
                >
                  {drafting ? "Adding…" : "Add more"}
                </button>
                <button
                  type="button"
                  disabled={confirming || confirm.ctaDisabled || !goalsOk}
                  onClick={() => void confirmPlan()}
                  className="text-xs px-3 py-1.5 rounded-md bg-emerald-500/20 text-emerald-50 border border-emerald-400/35 hover:bg-emerald-500/30 disabled:opacity-50"
                >
                  Confirm as-is / Fine
                </button>
              </div>
            </>
          ) : (
            <>
              <p className="text-[11px] text-sky-100/70">
                {morning?.auto_plan?.drafted
                  ? "Auto-drafted from routines + study seeds"
                  : "Draft from routines + light study seeds, then edit on the schedule"}
                {morning?.auto_plan?.created ? ` · ${morning.auto_plan.created} new` : ""}
              </p>
              {autoPlanTitles.length > 0 && (
                <ul className="text-xs text-sky-50/90 space-y-1 list-disc list-inside">
                  {autoPlanTitles.slice(0, 6).map((t) => (
                    <li key={t}>{t}</li>
                  ))}
                  {autoPlanTitles.length > 6 && (
                    <li className="list-none text-sky-100/60">+{autoPlanTitles.length - 6} more</li>
                  )}
                </ul>
              )}
              {draftError && <p className="text-[11px] text-rose-300">{draftError}</p>}
              <button
                type="button"
                disabled={drafting}
                onClick={() => void draftAutoPlan()}
                className="text-xs px-3 py-1.5 rounded-md bg-sky-500/25 text-sky-50 border border-sky-400/40 hover:bg-sky-500/35 disabled:opacity-50"
              >
                {drafting
                  ? "Drafting…"
                  : autoPlanTitles.length > 0
                    ? "Refresh auto plan"
                    : "Draft auto plan"}
              </button>
            </>
          )}
        </section>
      )}

      {morning?.enabled && (
        <section
          aria-labelledby="plan-blocks-heading"
          className="rounded-xl border border-white/10 bg-white/[0.03] p-3 space-y-2"
        >
          <h3
            id="plan-blocks-heading"
            className="text-sm font-medium text-foreground flex items-center gap-2"
          >
            <ListTodo size={14} className="text-violet-400 shrink-0" />
            Today’s blocks
            <span className="text-[11px] font-normal text-muted-foreground tabular-nums">
              · {todayBlocks.length}
            </span>
          </h3>
          {todayBlocks.length === 0 ? (
            <p className="text-[11px] text-muted-foreground">
              No blocks yet — use Auto plan above, apply routines in step 1, or click an hour on the
              schedule.
            </p>
          ) : (
            <ul className="space-y-1 max-h-36 overflow-y-auto pr-0.5">
              {todayBlocks.slice(0, 10).map((b) => (
                <li
                  key={b.id}
                  className="flex items-baseline justify-between gap-2 text-xs text-foreground/90"
                >
                  <span className="truncate min-w-0">{b.title}</span>
                  <span className="shrink-0 tabular-nums text-muted-foreground text-[11px]">
                    {formatBlockClock(b.start_at)}–{formatBlockClock(b.end_at)}
                  </span>
                </li>
              ))}
              {todayBlocks.length > 10 && (
                <li className="text-[11px] text-muted-foreground">
                  +{todayBlocks.length - 10} more on the schedule →
                </li>
              )}
            </ul>
          )}
          <p className="text-[10px] text-muted-foreground">
            Edit · move · delete on the day timeline to the right.
          </p>
        </section>
      )}

      {showConfirm && (
        <section
          aria-labelledby="plan-confirm-heading"
          className={`rounded-xl border p-3 space-y-2 ${
            morning?.plan_done
              ? "border-emerald-500/30 bg-emerald-500/10"
              : confirm.windowOpen
                ? "border-amber-500/35 bg-amber-500/10"
                : "border-white/15 bg-white/[0.03]"
          }`}
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3
              id="plan-confirm-heading"
              className={`text-sm font-medium flex items-center gap-2 ${
                morning?.plan_done ? "text-emerald-100" : "text-amber-100"
              }`}
            >
              {morning?.plan_done ? (
                <CheckCircle2 size={14} className="text-emerald-300 shrink-0" />
              ) : (
                <Clock size={14} className="text-amber-300 shrink-0" />
              )}
              Confirm
            </h3>
            <span
              className={`text-[10px] uppercase tracking-wide px-2 py-0.5 rounded-full border ${
                morning?.plan_done
                  ? "border-emerald-400/35 text-emerald-200/90"
                  : confirm.windowOpen
                    ? "border-amber-400/40 text-amber-100"
                    : "border-white/20 text-muted-foreground"
              }`}
            >
              {confirm.windowLabel}
            </span>
          </div>
          <p
            className={`text-[11px] ${
              morning?.plan_done ? "text-emerald-100/80" : "text-amber-100/75"
            }`}
          >
            {confirm.hint}
          </p>
          {morning?.plan_done ? (
            <div className="space-y-2">
              <p className="text-[11px] text-emerald-200/90">
                Morning complete
                {typeof morning.rewards?.total_points === "number" && morning.rewards.total_points > 0
                  ? ` — ${morning.rewards.total_points} pts today`
                  : ""}
                {morning.rewards?.awards?.bible?.granted || morning.rewards?.awards?.plan?.granted
                  ? ` (${[
                      morning.rewards?.awards?.bible?.granted
                        ? morning.rewards.awards.bible.label
                        : null,
                      morning.rewards?.awards?.plan?.granted
                        ? morning.rewards.awards.plan.label
                        : null,
                    ]
                      .filter(Boolean)
                      .join(", ")})`
                  : ""}
                .
              </p>
              {morning.daily_practice?.show ? (
                <Link
                  to={morning.daily_practice.to || "/review?tab=due"}
                  className="inline-flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-md bg-sky-500/20 text-sky-50 border border-sky-400/35 hover:bg-sky-500/30"
                >
                  {morning.daily_practice.label || "Daily practice"}
                  <span className="text-[10px] text-sky-100/70">optional</span>
                </Link>
              ) : null}
            </div>
          ) : (
            <>
              {!goalsOk && (
                <p
                  role="status"
                  className="text-[11px] text-rose-200 bg-rose-500/15 border border-rose-400/30 rounded-md px-2 py-1.5"
                >
                  Goals required — set a main goal in step 2 (Goals), then confirm.
                </p>
              )}
              {overcommit.level !== "ok" && (
                <div
                  className={`text-[11px] rounded-md px-2 py-1.5 border ${
                    overcommit.level === "over"
                      ? "border-rose-400/35 bg-rose-500/15 text-rose-100"
                      : "border-amber-400/35 bg-amber-500/10 text-amber-100"
                  }`}
                >
                  <p>{overcommit.message}</p>
                  {overcommit.level === "over" && (
                    <label className="mt-2 flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={overcommitAck}
                        onChange={(e) => setOvercommitAck(e.target.checked)}
                      />
                      Confirm anyway (over capacity)
                    </label>
                  )}
                </div>
              )}
              {confirmError && <p className="text-[11px] text-rose-300">{confirmError}</p>}
              <button
                type="button"
                disabled={confirming || confirm.ctaDisabled || !goalsOk}
                onClick={() => void confirmPlan()}
                className="text-xs px-3 py-1.5 rounded-md bg-amber-500/25 text-amber-50 border border-amber-400/40 hover:bg-amber-500/35 disabled:opacity-50"
              >
                {confirming ? "Confirming…" : confirm.ctaLabel}
              </button>
            </>
          )}
        </section>
      )}

      {morning?.enabled &&
        morning.next === "open" &&
        !morning.plan_done &&
        morning.plan_window?.phase === "after_eod" && (
          <p className="text-[11px] text-amber-200/80 px-0.5">{confirm.hint}</p>
        )}
    </div>
  );
}
