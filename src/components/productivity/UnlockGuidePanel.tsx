/**
 * Settings → Unlock: available counts + conditions for free SoftLand.
 * SoftLand free ≠ Arm. Goal minutes are edited on Plan → Goals, not here.
 */
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router";
import { Gift, Loader2, Target, Ticket } from "lucide-react";
import {
  fetchDistractionGate,
  type DistractionGate,
} from "../../api/behaviorClient";
import { requestBibleDayPass, requestRewardDay } from "../../api/bibleClient";
import { GOALS_UPDATED_EVENT } from "./ProductivityGoalsPanel";
import { formatHoursMins, formatHoursMinsPair } from "../../utils/formatDuration";
import { useFocusStatus } from "../../hooks/useFocusStatus";
import { cn } from "../../app/components/ui/utils";

type Props = {
  onSaved?: () => void;
};

export function UnlockGuidePanel({ onSaved }: Props) {
  const status = useFocusStatus();
  const [gate, setGate] = useState<DistractionGate | null>(null);
  const [loading, setLoading] = useState(true);
  const [busyClaim, setBusyClaim] = useState<"reward" | "pass" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [hint, setHint] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setGate(await fetchDistractionGate().catch(() => null));
    } catch (e: unknown) {
      const raw = e instanceof Error ? e.message : "Failed to load unlock status";
      setError(
        raw === "Failed to fetch"
          ? "Can't reach Focus data — open calt_focus or start the enforcer."
          : raw,
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    const onGoals = () => void load();
    window.addEventListener(GOALS_UPDATED_EVENT, onGoals);
    return () => window.removeEventListener(GOALS_UPDATED_EVENT, onGoals);
  }, [load]);

  useEffect(() => {
    if (!hint) return;
    const t = window.setTimeout(() => setHint(null), 6000);
    return () => window.clearTimeout(t);
  }, [hint]);

  const claimReward = async () => {
    const ok = window.prompt(
      "Use one earned reward day? SoftLand free until midnight. Type REWARD:",
    );
    if (ok !== "REWARD") return;
    setBusyClaim("reward");
    setError(null);
    try {
      const r = await requestRewardDay("REWARD");
      setGate(await fetchDistractionGate().catch(() => null));
      setHint(r.message || "Reward day active — free until midnight.");
      onSaved?.();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Reward day failed");
    } finally {
      setBusyClaim(null);
    }
  };

  const claimPass = async () => {
    const ok = window.prompt("Use one day pass? SoftLand free until midnight. Type PASS:");
    if (ok !== "PASS") return;
    setBusyClaim("pass");
    setError(null);
    try {
      const r = await requestBibleDayPass("PASS");
      setGate(await fetchDistractionGate().catch(() => null));
      setHint(r.message || "Day pass active until midnight.");
      onSaved?.();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Day pass failed");
    } finally {
      setBusyClaim(null);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground py-4">
        <Loader2 size={14} className="animate-spin" /> Loading unlock status…
      </div>
    );
  }

  const freeActive = Boolean(gate?.day_unlimited || gate?.reward_day || gate?.day_pass);
  const freeUntil = String(status.softland?.runtime?.free_until || "").trim();
  const goalMin = gate?.daily_goal_minutes ?? 0;
  const doneMin = gate?.productive_minutes ?? 0;
  const goalMetToday = goalMin > 0 && doneMin >= goalMin;
  const rewardsAvailable = gate?.reward_day_status?.available ?? 0;
  const daysToNext = gate?.reward_day_status?.days_to_next_reward ?? 4;
  const qualifying = gate?.reward_day_status?.qualifying_days ?? 0;
  const perReward = gate?.reward_day_status?.qualifying_days_per_reward ?? 4;
  const passesLeft = gate?.day_pass_status?.remaining ?? 0;
  const passesLimit = gate?.day_pass_status?.limit ?? 2;
  const passesUsed = gate?.day_pass_status?.used ?? Math.max(0, passesLimit - passesLeft);

  return (
    <div className="space-y-5">
      <p className="max-w-2xl text-[13px] leading-relaxed text-muted-foreground">
        SoftLand free until midnight. Not Arm. Change the daily goal on{" "}
        <Link to="/productivity?tab=plan" className="underline text-foreground/80 hover:text-foreground">
          Plan → Goals
        </Link>
        .
      </p>

      {freeActive ? (
        <div className="rounded-xl border border-teal-400/30 bg-teal-500/10 px-4 py-3 text-[13px] text-teal-100">
          Free SoftLand is active today
          {freeUntil ? ` · until ${freeUntil}` : ""}.
        </div>
      ) : null}

      <div className="grid gap-3 lg:grid-cols-3">
        {/* Goal met — automatic unlock; show goal as condition, not an editor */}
        <article className="rounded-xl border border-teal-400/25 bg-teal-500/[0.06] p-4 space-y-3">
          <div className="flex items-start justify-between gap-2">
            <div className="flex items-center gap-2">
              <Target size={16} className="text-teal-200" aria-hidden />
              <h3 className="text-[14px] font-semibold text-foreground">Goal met</h3>
            </div>
            <span className="rounded-full border border-teal-400/30 bg-teal-500/15 px-2.5 py-0.5 text-[11px] font-semibold tabular-nums text-teal-100">
              {goalMetToday || freeActive ? "Unlocked" : "Locked"}
            </span>
          </div>
          <p className="text-[28px] font-semibold tabular-nums leading-none text-foreground">
            {formatHoursMinsPair(doneMin, goalMin || 240)}
          </p>
          <p className="text-[12px] leading-relaxed text-muted-foreground">
            Condition: after Bible + Confirm, hit today’s daily goal (
            <span className="text-foreground/90">{formatHoursMins(goalMin || 240)}</span>
            ). Then SoftLand is free until midnight — no spend needed.
          </p>
          <p className="text-[11px] text-muted-foreground">
            Still on: adult filter · Arm · app time budgets.
          </p>
        </article>

        {/* Reward day — banked count + earn condition tied to daily goal */}
        <article className="rounded-xl border border-sky-400/25 bg-sky-500/[0.06] p-4 space-y-3">
          <div className="flex items-start justify-between gap-2">
            <div className="flex items-center gap-2">
              <Gift size={16} className="text-sky-200" aria-hidden />
              <h3 className="text-[14px] font-semibold text-foreground">Reward day</h3>
            </div>
            <span className="rounded-full border border-sky-400/30 bg-sky-500/15 px-2.5 py-0.5 text-[11px] font-semibold tabular-nums text-sky-100">
              {rewardsAvailable} available
            </span>
          </div>
          <p className="text-[28px] font-semibold tabular-nums leading-none text-foreground">
            {rewardsAvailable}
            <span className="ml-1.5 text-[13px] font-normal text-muted-foreground">banked</span>
          </p>
          <p className="text-[12px] leading-relaxed text-muted-foreground">
            Condition: complete the{" "}
            <span className="text-foreground/90">daily goal</span> + one Bible chapter on{" "}
            <span className="text-foreground/90">{perReward} days</span> to bank 1. Progress{" "}
            <span className="tabular-nums text-foreground/90">
              {qualifying}/{perReward}
            </span>
            {rewardsAvailable <= 0 ? (
              <>
                {" "}
                · <span className="tabular-nums">{daysToNext}</span> day(s) to next.
              </>
            ) : null}{" "}
            Spend for SoftLand free until midnight.
          </p>
          <button
            type="button"
            disabled={Boolean(busyClaim) || freeActive || rewardsAvailable <= 0}
            onClick={() => void claimReward()}
            className="inline-flex min-h-10 w-full items-center justify-center gap-1.5 rounded-lg border border-sky-400/30 bg-sky-500/15 px-3 text-[12px] text-sky-100 hover:bg-sky-500/25 disabled:opacity-40"
          >
            {busyClaim === "reward" ? <Loader2 size={12} className="animate-spin" /> : <Gift size={12} />}
            {freeActive
              ? "Free already active"
              : rewardsAvailable > 0
                ? `Use reward day (${rewardsAvailable})`
                : "None banked yet"}
          </button>
        </article>

        {/* Day pass — weekly quota */}
        <article className="rounded-xl border border-amber-400/25 bg-amber-500/[0.06] p-4 space-y-3">
          <div className="flex items-start justify-between gap-2">
            <div className="flex items-center gap-2">
              <Ticket size={16} className="text-amber-200" aria-hidden />
              <h3 className="text-[14px] font-semibold text-foreground">Day pass</h3>
            </div>
            <span className="rounded-full border border-amber-400/30 bg-amber-500/15 px-2.5 py-0.5 text-[11px] font-semibold tabular-nums text-amber-100">
              {passesLeft} left
            </span>
          </div>
          <p className="text-[28px] font-semibold tabular-nums leading-none text-foreground">
            {passesLeft}
            <span className="ml-1.5 text-[13px] font-normal text-muted-foreground">
              / {passesLimit} this week
            </span>
          </p>
          <p className="text-[12px] leading-relaxed text-muted-foreground">
            Condition: Bible done, then spend a pass. Quota{" "}
            <span className="text-foreground/90">{passesLimit}/week</span>
            {passesUsed > 0 ? (
              <>
                {" "}
                · used <span className="tabular-nums">{passesUsed}</span>
              </>
            ) : null}
            . SoftLand free until midnight — does not Arm.
          </p>
          <button
            type="button"
            disabled={Boolean(busyClaim) || freeActive || passesLeft <= 0}
            onClick={() => void claimPass()}
            className="inline-flex min-h-10 w-full items-center justify-center gap-1.5 rounded-lg border border-amber-400/30 bg-amber-500/15 px-3 text-[12px] text-amber-100 hover:bg-amber-500/25 disabled:opacity-40"
          >
            {busyClaim === "pass" ? <Loader2 size={12} className="animate-spin" /> : <Ticket size={12} />}
            {freeActive
              ? "Free already active"
              : passesLeft > 0
                ? `Use day pass (${passesLeft} left)`
                : "No passes left"}
          </button>
        </article>
      </div>

      <p className="text-[11px] text-muted-foreground">
        Bible → Plan → Confirm still gates the morning. Free SoftLand ≠ Disarm — kill list is under{" "}
        <Link
          to="/productivity?tab=settings&section=apps"
          className="underline text-foreground/80 hover:text-foreground"
        >
          Blocks → Apps
        </Link>
        .
      </p>

      {hint ? <p className="text-[12px] text-teal-200/90">{hint}</p> : null}
      {error ? (
        <p className="text-[12px] text-rose-300">
          {error}{" "}
          <button type="button" className="underline" onClick={() => void load()}>
            Retry
          </button>
        </p>
      ) : null}
    </div>
  );
}

export default UnlockGuidePanel;
