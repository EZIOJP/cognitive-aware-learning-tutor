import { useState } from "react";
import { Button } from "../../app/components/ui/button";
import type { PlannerBlock } from "../../api/plannerClient";
import { formatHoursMins } from "../../utils/formatDuration";

type Props = {
  block: PlannerBlock;
  /** Plan tab = schedule only (delete). Calendar = start / done / partial / roll. */
  mode?: "plan" | "track";
  onStart: () => Promise<void>;
  onComplete: (minutes?: number) => Promise<void>;
  onRollForward: () => Promise<void>;
  onDelete: () => Promise<void>;
  onClose: () => void;
};

export function PlannerBlockActions({
  block,
  mode = "track",
  onStart,
  onComplete,
  onRollForward,
  onDelete,
  onClose,
}: Props) {
  const [partialMin, setPartialMin] = useState(Math.min(30, block.remaining_minutes));
  const [busy, setBusy] = useState(false);

  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    try {
      await fn();
    } finally {
      setBusy(false);
    }
  };

  const statusLabel =
    block.status === "done"
      ? "Done"
      : block.status === "rolled"
        ? "Rolled"
        : block.status === "in_progress"
          ? "In progress"
          : "Scheduled";

  const showTrack = mode === "track" && block.status !== "done" && block.status !== "rolled";

  return (
    <div
      className={
        mode === "track"
          ? "space-y-3 p-4 rounded-xl border border-emerald-500/35 bg-gradient-to-b from-slate-900 via-emerald-950/40 to-slate-950 shadow-lg"
          : "space-y-3 p-4 rounded-lg border border-violet-500/30 bg-card"
      }
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-[10px] uppercase tracking-wider text-emerald-300/70 font-medium">
            {mode === "track" ? "Track this block" : "Scheduled block"}
          </p>
          <h3 className="text-sm font-semibold text-foreground">{block.title}</h3>
          <p className="text-xs text-muted-foreground mt-0.5">
            {block.category} · {statusLabel} · {formatHoursMins(block.remaining_minutes)} left of{" "}
            {formatHoursMins(block.planned_minutes)}
          </p>
          {mode === "plan" ? (
            <p className="text-[11px] text-muted-foreground mt-1.5">
              Scheduling view — use the Calendar tab to start or mark blocks done.
            </p>
          ) : null}
        </div>
        <Button type="button" variant="ghost" size="sm" onClick={onClose}>
          Close
        </Button>
      </div>

      {showTrack && (
        <div className="flex flex-col gap-2">
          <Button
            type="button"
            size="default"
            className="w-full bg-emerald-600 hover:bg-emerald-500 text-white font-semibold"
            disabled={busy}
            onClick={() => void run(() => onComplete())}
            title="Count the full remaining time as completed"
          >
            {block.status === "in_progress" ? "Finish — mark done" : "Mark done"}
          </Button>
          {block.status !== "in_progress" && (
            <Button type="button" size="sm" variant="outline" disabled={busy} onClick={() => void run(onStart)}>
              Start
            </Button>
          )}
        </div>
      )}

      {showTrack && block.remaining_minutes > 0 && (
        <div className="flex flex-wrap items-end gap-2 border-t border-border pt-3">
          <label className="text-xs text-muted-foreground">
            Partial (min)
            <input
              type="number"
              min={1}
              max={block.remaining_minutes}
              className="mt-1 block w-20 rounded border border-border bg-background px-2 py-1 text-sm"
              value={partialMin}
              onChange={(e) => setPartialMin(Number(e.target.value))}
            />
          </label>
          <Button
            type="button"
            size="sm"
            variant="secondary"
            disabled={busy}
            onClick={() => void run(() => onComplete(partialMin))}
          >
            Log partial
          </Button>
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={busy}
            onClick={() => void run(onRollForward)}
          >
            Roll forward ({formatHoursMins(block.remaining_minutes)})
          </Button>
        </div>
      )}

      <Button
        type="button"
        size="sm"
        variant="ghost"
        className="text-red-400"
        disabled={busy}
        onClick={() => void run(onDelete)}
      >
        Delete block
      </Button>
    </div>
  );
}
