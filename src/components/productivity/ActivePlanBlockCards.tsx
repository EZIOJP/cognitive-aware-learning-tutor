import { useCallback, useEffect, useMemo, useState } from "react";
import {
  CheckCircle2,
  Clock,
  Loader2,
  Play,
  SkipForward,
  Sparkles,
} from "lucide-react";
import {
  completePlannerBlock,
  fetchPlannerBlocks,
  rollForwardPlannerBlock,
  startPlannerBlock,
  type PlannerBlock,
} from "../../api/plannerClient";
import { isFocusDesktopShell } from "../../utils/focusDesktopShell";
import { cn } from "../../app/components/ui/utils";

function gateModeForBlock(block: PlannerBlock): "free" | "study" | "none" {
  const c = (block.category || "").trim().toLowerCase();
  const t = (block.title || "").trim().toLowerCase();
  if (
    c === "spiritual" ||
    t.includes("bible") ||
    t.includes("prayer") ||
    c === "study" ||
    c === "coursework" ||
    c === "work" ||
    t.includes("scaler") ||
    t.includes("sleep")
  ) {
    return "study";
  }
  if (
    c === "break" ||
    c === "free" ||
    c === "reward" ||
    c === "leisure" ||
    c === "rest" ||
    t.includes("free time")
  ) {
    return "free";
  }
  return "none";
}

function formatRange(startIso: string, endIso: string): string {
  try {
    const a = new Date(startIso);
    const b = new Date(endIso);
    const opts: Intl.DateTimeFormatOptions = { hour: "numeric", minute: "2-digit" };
    return `${a.toLocaleTimeString([], opts)} – ${b.toLocaleTimeString([], opts)}`;
  } catch {
    return "—";
  }
}

function minutesLeft(endIso: string, now: Date): number {
  try {
    return Math.max(0, Math.round((new Date(endIso).getTime() - now.getTime()) / 60000));
  } catch {
    return 0;
  }
}

function pickActiveAndNext(blocks: PlannerBlock[], now: Date): {
  active: PlannerBlock | null;
  next: PlannerBlock | null;
} {
  const open = blocks.filter(
    (b) => b.status !== "done" && b.status !== "cancelled" && b.status !== "rolled",
  );
  let active: PlannerBlock | null = null;
  let next: PlannerBlock | null = null;
  for (const b of open) {
    const start = new Date(b.start_at).getTime();
    const end = new Date(b.end_at).getTime();
    const t = now.getTime();
    if (start <= t && t < end) {
      active = b;
      break;
    }
  }
  const upcoming = open
    .filter((b) => new Date(b.start_at).getTime() > now.getTime())
    .sort((a, b) => new Date(a.start_at).getTime() - new Date(b.start_at).getTime());
  next = upcoming[0] ?? null;
  return { active, next };
}

type Props = {
  day: Date;
  refreshKey?: number;
  onChanged?: () => void;
};

/**
 * Focus / Calendar glance: active + next plan blocks as gloss cards.
 */
export function ActivePlanBlockCards({ day, refreshKey = 0, onChanged }: Props) {
  const [blocks, setBlocks] = useState<PlannerBlock[]>([]);
  const [now, setNow] = useState(() => new Date());
  const [busyId, setBusyId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const start = new Date(day);
      start.setHours(0, 0, 0, 0);
      const end = new Date(day);
      end.setHours(23, 59, 59, 999);
      const list = await fetchPlannerBlocks(start, end);
      setBlocks(list);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Could not load plan blocks";
      setError(
        msg === "enforcer_unreachable"
          ? "Enforcer unreachable — open this in calt_focus.exe (pipe bridge) or start the enforcer."
          : msg,
      );
      setBlocks([]);
    } finally {
      setLoading(false);
    }
  }, [day]);

  useEffect(() => {
    void load();
  }, [load, refreshKey]);

  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), 30_000);
    return () => window.clearInterval(id);
  }, []);

  const { active, next } = useMemo(() => pickActiveAndNext(blocks, now), [blocks, now]);

  const run = async (id: number, fn: () => Promise<unknown>) => {
    setBusyId(id);
    setError(null);
    try {
      await fn();
      await load();
      onChanged?.();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Action failed");
    } finally {
      setBusyId(null);
    }
  };

  if (!isFocusDesktopShell() && !loading && !active && !next) {
    // Study interstitial path — still useful but keep quiet if empty
  }

  if (loading && blocks.length === 0) {
    return (
      <div className="flex items-center gap-2 text-xs text-muted-foreground py-2">
        <Loader2 size={14} className="animate-spin" /> Loading today&apos;s blocks…
      </div>
    );
  }

  if (!active && !next) {
    return (
      <div className="rounded-2xl border border-dashed border-white/15 bg-white/[0.02] px-4 py-3">
        <p className="text-sm font-medium text-foreground/90">No active block</p>
        <p className="text-[11px] text-muted-foreground mt-0.5">
          Open Plan to schedule focus time — SoftLand follows free/study blocks automatically.
        </p>
        {error ? <p className="text-[11px] text-rose-300 mt-1">{error}</p> : null}
      </div>
    );
  }

  const Card = ({
    block,
    kind,
  }: {
    block: PlannerBlock;
    kind: "active" | "next";
  }) => {
    const mode = gateModeForBlock(block);
    const left = minutesLeft(block.end_at, now);
    const busy = busyId === block.id;
    return (
      <div
        className={cn(
          "rounded-2xl border px-4 py-3 space-y-2 gloss-panel",
          kind === "active"
            ? "border-emerald-500/30 bg-emerald-500/[0.07]"
            : "border-white/10 bg-white/[0.03]",
        )}
      >
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wide text-muted-foreground">
              {kind === "active" ? (
                <>
                  <Sparkles size={11} className="text-emerald-300" /> Now
                </>
              ) : (
                <>
                  <Clock size={11} /> Up next
                </>
              )}
              <span className="text-white/20">·</span>
              <span className="tabular-nums normal-case">{block.category || "study"}</span>
            </div>
            <h4 className="text-sm font-semibold text-foreground truncate mt-0.5">{block.title}</h4>
            <p className="text-[11px] text-muted-foreground tabular-nums mt-0.5">
              {formatRange(block.start_at, block.end_at)}
              {kind === "active" ? ` · ${left}m left` : null}
            </p>
          </div>
          <span
            className={cn(
              "shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium border",
              mode === "free"
                ? "border-sky-400/40 bg-sky-500/15 text-sky-100"
                : mode === "study"
                  ? "border-amber-400/40 bg-amber-500/15 text-amber-100"
                  : "border-white/15 bg-white/5 text-muted-foreground",
            )}
          >
            SoftLand {mode === "none" ? "unchanged" : mode}
          </span>
        </div>
        {kind === "active" ? (
          <div className="flex flex-wrap gap-1.5 pt-1">
            {block.status !== "in_progress" ? (
              <button
                type="button"
                disabled={busy}
                onClick={() => void run(block.id, () => startPlannerBlock(block.id))}
                className="inline-flex items-center gap-1 rounded-lg bg-emerald-600/80 hover:bg-emerald-600 px-2.5 py-1 text-[11px] disabled:opacity-50"
              >
                <Play size={11} /> Start
              </button>
            ) : (
              <span className="inline-flex items-center gap-1 text-[11px] text-emerald-200/90">
                <CheckCircle2 size={12} /> In progress
              </span>
            )}
            <button
              type="button"
              disabled={busy}
              onClick={() => void run(block.id, () => completePlannerBlock(block.id))}
              className="inline-flex items-center gap-1 rounded-lg border border-white/15 px-2.5 py-1 text-[11px] hover:bg-white/5 disabled:opacity-50"
            >
              <CheckCircle2 size={11} /> Complete
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => void run(block.id, () => rollForwardPlannerBlock(block.id))}
              className="inline-flex items-center gap-1 rounded-lg border border-white/15 px-2.5 py-1 text-[11px] hover:bg-white/5 disabled:opacity-50"
              title="Mark rolled and reschedule remaining time"
            >
              <SkipForward size={11} /> Roll forward
            </button>
          </div>
        ) : null}
      </div>
    );
  };

  return (
    <div className="space-y-2">
      <div className="grid gap-2 sm:grid-cols-2">
        {active ? <Card block={active} kind="active" /> : null}
        {next ? <Card block={next} kind="next" /> : null}
        {active && !next ? (
          <div className="rounded-2xl border border-dashed border-white/10 bg-transparent px-4 py-3 flex items-center text-[11px] text-muted-foreground">
            Nothing scheduled after this block.
          </div>
        ) : null}
      </div>
      {error ? <p className="text-[11px] text-rose-300">{error}</p> : null}
    </div>
  );
}

export default ActivePlanBlockCards;
