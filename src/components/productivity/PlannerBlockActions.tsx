import { useState } from "react";
import { Button } from "../../app/components/ui/button";
import type { PlannerBlock } from "../../api/plannerClient";

type Props = {
  block: PlannerBlock;
  onStart: () => Promise<void>;
  onComplete: (minutes?: number) => Promise<void>;
  onRollForward: () => Promise<void>;
  onDelete: () => Promise<void>;
  onClose: () => void;
};

export function PlannerBlockActions({
  block,
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

  return (
    <div className="space-y-3 p-4 rounded-lg border border-violet-500/30 bg-card">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-foreground">{block.title}</h3>
          <p className="text-xs text-muted-foreground mt-0.5">
            {block.category} · {statusLabel} · {block.remaining_minutes}m left of {block.planned_minutes}m
          </p>
        </div>
        <Button type="button" variant="ghost" size="sm" onClick={onClose}>
          Close
        </Button>
      </div>

      {block.status !== "done" && block.status !== "rolled" && (
        <div className="flex flex-wrap gap-2">
          {block.status !== "in_progress" && (
            <Button type="button" size="sm" variant="outline" disabled={busy} onClick={() => void run(onStart)}>
              Start
            </Button>
          )}
          <Button
            type="button"
            size="sm"
            disabled={busy}
            onClick={() => void run(() => onComplete())}
          >
            Mark done
          </Button>
        </div>
      )}

      {block.status !== "done" && block.status !== "rolled" && block.remaining_minutes > 0 && (
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
            Roll forward ({block.remaining_minutes}m)
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
