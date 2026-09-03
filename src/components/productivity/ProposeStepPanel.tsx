import { useEffect, useMemo, useState } from "react";
import {
  CalendarDays,
  ChevronDown,
  ChevronRight,
  Layers,
  Loader2,
  Sparkles,
  Wand2,
} from "lucide-react";
import type { ApplyPlanRange } from "./ProposePlanPreview";
import { resolveProposedOverlaps } from "./resolveProposedOverlaps";
import type { ProposedPlannerBlock } from "../../api/plannerClient";
import { MAX_PRODUCTIVITY_EXPORT_DAYS } from "../../api/plannerClient";

export type ProposeHorizon = "day" | "week" | "month" | "custom";

type Props = {
  horizon: ProposeHorizon;
  onHorizonChange: (h: ProposeHorizon) => void;
  customHorizonDays: number;
  onCustomHorizonDaysChange: (n: number) => void;
  /** Inclusive day count for the selected horizon (1 / 7 / 30 / custom). */
  horizonDays: number;
  /** YYYY-MM-DD local start (today). */
  rangeStart: string;
  exportDays: number;
  onExportDaysChange: (n: number) => void;
  proposing: boolean;
  onGenerate: (mode: "smart" | "review" | "full") => void;
  exportHint?: string | null;
  proposed: ProposedPlannerBlock[] | null;
  proposeMeta: {
    rationale?: string | null;
    used_llm?: boolean;
    scaled_daily_hours?: number | null;
  } | null;
  onProposedChange: (blocks: ProposedPlannerBlock[]) => void;
  onApply: (range: ApplyPlanRange) => void;
  onDismissDraft: () => void;
};

const HORIZON_OPTIONS: { id: ProposeHorizon; label: string; hint: string }[] = [
  { id: "day", label: "Today", hint: "Rest of today only" },
  { id: "week", label: "This week", hint: "Today + next 6 days" },
  { id: "month", label: "This month", hint: "Next 30 days" },
  { id: "custom", label: "Custom", hint: "Choose day count" },
];

function dayKeysFrom(startYmd: string, count: number): string[] {
  const [y, m, d] = startYmd.split("-").map(Number);
  const base = new Date(y, m - 1, d);
  const out: string[] = [];
  for (let i = 0; i < count; i++) {
    const cur = new Date(base);
    cur.setDate(base.getDate() + i);
    out.push(
      `${cur.getFullYear()}-${String(cur.getMonth() + 1).padStart(2, "0")}-${String(cur.getDate()).padStart(2, "0")}`,
    );
  }
  return out;
}

function horizonApplyLabel(horizon: ProposeHorizon, days: number): string {
  if (horizon === "day") return "Apply today";
  if (horizon === "week") return "Apply this week";
  if (horizon === "month") return "Apply this month";
  return `Apply ${days} days`;
}

function studyHours(blocks: ProposedPlannerBlock[]): number {
  return (
    blocks
      .filter((b) => b.source !== "existing" && b.source !== "routine" && b.source !== "break")
      .reduce((sum, b) => {
        const ms = new Date(b.end_at).getTime() - new Date(b.start_at).getTime();
        return sum + Math.max(0, ms) / 3_600_000;
      }, 0)
  );
}

export function ProposeStepPanel({
  horizon,
  onHorizonChange,
  customHorizonDays,
  onCustomHorizonDaysChange,
  horizonDays,
  rangeStart,
  exportDays,
  onExportDaysChange,
  proposing,
  onGenerate,
  exportHint,
  proposed,
  proposeMeta,
  onProposedChange,
  onApply,
  onDismissDraft,
}: Props) {
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [exportDaysText, setExportDaysText] = useState(String(exportDays));
  useEffect(() => {
    setExportDaysText(String(exportDays));
  }, [exportDays]);
  const blocks = proposed || [];
  const hasDraft = blocks.length > 0;

  const applyDays = useMemo(() => dayKeysFrom(rangeStart, horizonDays), [rangeStart, horizonDays]);
  const applyLabel = horizonApplyLabel(horizon, horizonDays);
  const editable = blocks.filter((b) => b.source !== "existing");
  const plannedH = studyHours(blocks);

  const applyHorizon = () => {
    onApply({
      from: applyDays[0],
      to: applyDays[applyDays.length - 1],
      days: applyDays,
      label: applyLabel,
    });
  };

  const applyToday = () => {
    onApply({
      from: rangeStart,
      to: rangeStart,
      days: [rangeStart],
      label: "Today",
    });
  };

  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 space-y-4">
      <div>
        <h2 className="text-sm font-semibold text-foreground">3 · Build your schedule</h2>
        <p className="text-xs text-muted-foreground mt-1 leading-relaxed">
          Pick how far ahead, generate once, edit on the calendar to the right, then apply that same range.
        </p>
      </div>

      <div className="rounded-xl border border-white/10 bg-black/20 p-4 space-y-4">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground mb-2">
            Build &amp; apply range
          </p>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            {HORIZON_OPTIONS.map(({ id, label, hint }) => (
              <button
                key={id}
                type="button"
                title={hint}
                onClick={() => onHorizonChange(id)}
                className={`rounded-xl px-2 py-2.5 text-left border transition-colors ${
                  horizon === id
                    ? "border-primary/50 bg-primary/20 text-foreground"
                    : "border-white/10 bg-black/30 text-muted-foreground hover:bg-white/5"
                }`}
              >
                <span className="block text-xs font-medium">{label}</span>
                <span className="block text-[10px] opacity-70 mt-0.5 leading-tight">{hint}</span>
              </button>
            ))}
          </div>
          {horizon === "custom" && (
            <label className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
              Days ahead
              <input
                type="number"
                min={1}
                max={62}
                value={customHorizonDays}
                onChange={(e) =>
                  onCustomHorizonDaysChange(Math.max(1, Math.min(62, Number(e.target.value) || 14)))
                }
                className="w-16 rounded-lg border border-white/10 bg-black/40 px-2 py-1.5 text-foreground"
              />
            </label>
          )}
          <p className="mt-2 text-[10px] text-muted-foreground">
            Selected: <span className="text-foreground/90">{applyLabel.replace(/^Apply /, "")}</span>
            {" · "}
            {horizonDays} day{horizonDays === 1 ? "" : "s"} from today
          </p>
        </div>

        <button
          type="button"
          disabled={proposing}
          onClick={() => onGenerate("smart")}
          className="w-full flex items-center justify-center gap-2 rounded-xl bg-primary px-4 py-3 text-sm font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-50 shadow-sm"
        >
          {proposing ? <Loader2 size={16} className="animate-spin" /> : <CalendarDays size={16} />}
          {hasDraft ? "Regenerate schedule" : "Generate schedule"}
        </button>

        {hasDraft && (
          <button
            type="button"
            disabled={proposing}
            onClick={() => onGenerate("review")}
            className="w-full flex items-center justify-center gap-2 rounded-xl border border-primary/35 bg-primary/10 px-3 py-2.5 text-xs font-medium text-foreground hover:bg-primary/20 disabled:opacity-50"
          >
            <Wand2 size={14} />
            Improve draft with AI
          </button>
        )}

        <button
          type="button"
          onClick={() => setAdvancedOpen((o) => !o)}
          className="w-full flex items-center justify-between gap-2 text-xs text-muted-foreground hover:text-foreground py-1"
        >
          <span className="inline-flex items-center gap-1">
            {advancedOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            Advanced options
          </span>
          {!advancedOpen && <span className="text-[10px]">history · full AI rebuild</span>}
        </button>

        {advancedOpen && (
          <div className="space-y-3 pt-1 border-t border-white/10">
            <label className="block text-xs text-muted-foreground space-y-1">
              <span>History lookback (days)</span>
              <span className="block text-[10px] leading-snug">
                Uses recent tracker data for block lengths. Default 7 is fine. Up to 1 year (
                {MAX_PRODUCTIVITY_EXPORT_DAYS} days).
              </span>
              <input
                type="number"
                inputMode="numeric"
                min={1}
                max={MAX_PRODUCTIVITY_EXPORT_DAYS}
                value={exportDaysText}
                onChange={(e) => {
                  const raw = e.target.value;
                  setExportDaysText(raw);
                  if (raw.trim() === "") return;
                  const n = Number(raw);
                  if (!Number.isFinite(n) || n < 1) return;
                  if (n <= MAX_PRODUCTIVITY_EXPORT_DAYS) {
                    onExportDaysChange(Math.floor(n));
                  }
                }}
                onBlur={() => {
                  const n = Number(exportDaysText);
                  const clamped = Math.max(
                    1,
                    Math.min(
                      MAX_PRODUCTIVITY_EXPORT_DAYS,
                      Number.isFinite(n) && n >= 1 ? Math.floor(n) : exportDays || 7,
                    ),
                  );
                  onExportDaysChange(clamped);
                  setExportDaysText(String(clamped));
                }}
                className="mt-1 w-20 rounded-lg border border-white/10 bg-black/40 px-2 py-1.5 text-foreground"
              />
            </label>
            <button
              type="button"
              disabled={proposing}
              onClick={() => onGenerate("full")}
              className="w-full flex items-center justify-center gap-2 rounded-xl border border-white/15 bg-white/5 px-3 py-2 text-xs text-muted-foreground hover:bg-white/10 hover:text-foreground disabled:opacity-50"
            >
              <Sparkles size={14} />
              Rebuild from scratch with AI
            </button>
          </div>
        )}

        {exportHint ? (
          <p
            className="text-[11px] text-sky-300 break-words rounded-lg bg-sky-500/10 border border-sky-500/20 px-2.5 py-2"
            title={exportHint}
          >
            {exportHint}
          </p>
        ) : !hasDraft ? (
          <p className="text-[11px] text-muted-foreground text-center">
            Tip: set routines &amp; goals first — then generate.
          </p>
        ) : null}
      </div>

      {hasDraft && (
        <div className="rounded-xl border border-primary/30 bg-primary/5 p-4 space-y-3">
          <div>
            <h3 className="text-sm font-semibold text-foreground">Draft ready</h3>
            <p className="text-xs text-muted-foreground mt-1">
              Edit times on the <span className="text-foreground/90">Schedule preview</span> to the right.
              Apply uses the same range you picked above
              {horizon === "week" ? " (this week = 7 days)" : ""}.
            </p>
            <div className="mt-2 flex flex-wrap gap-1.5 text-[10px]">
              <span className="rounded-md border border-white/15 bg-black/30 px-2 py-0.5 text-muted-foreground">
                {editable.length} new blocks · {plannedH.toFixed(1)}h study
              </span>
              {proposeMeta?.used_llm ? (
                <span className="rounded-md border border-primary/30 bg-primary/10 px-2 py-0.5 text-primary">
                  AI
                </span>
              ) : (
                <span className="rounded-md border border-white/15 bg-black/30 px-2 py-0.5 text-muted-foreground">
                  Smart rules
                </span>
              )}
            </div>
            {proposeMeta?.rationale ? (
              <p className="mt-2 text-[11px] text-muted-foreground line-clamp-2" title={proposeMeta.rationale}>
                {proposeMeta.rationale}
              </p>
            ) : null}
          </div>

          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              disabled={proposing || editable.length === 0}
              onClick={applyHorizon}
              className="inline-flex flex-1 min-w-[10rem] items-center justify-center gap-1.5 rounded-xl bg-primary px-3 py-2.5 text-xs font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
            >
              {proposing ? <Loader2 size={14} className="animate-spin" /> : <CalendarDays size={14} />}
              {applyLabel}
            </button>
            {horizon !== "day" ? (
              <button
                type="button"
                disabled={proposing || editable.length === 0}
                onClick={applyToday}
                className="rounded-xl border border-white/15 px-3 py-2.5 text-xs text-muted-foreground hover:bg-white/5 hover:text-foreground disabled:opacity-50"
              >
                Today only
              </button>
            ) : null}
          </div>

          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              disabled={proposing}
              onClick={() => onProposedChange(resolveProposedOverlaps(blocks))}
              className="inline-flex items-center gap-1 rounded-lg border border-amber-500/35 bg-amber-500/10 px-2.5 py-1.5 text-xs text-amber-100 hover:bg-amber-500/20 disabled:opacity-50"
            >
              <Layers size={12} />
              Fix overlaps
            </button>
            <button
              type="button"
              onClick={onDismissDraft}
              className="rounded-lg border border-white/10 px-2.5 py-1.5 text-xs hover:bg-white/5"
            >
              Discard draft
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

/** Shared helper for footer / other callers — same day set as the panel. */
export function applyRangeForHorizon(
  rangeStart: string,
  horizonDays: number,
  horizon: ProposeHorizon,
): ApplyPlanRange {
  const days = dayKeysFrom(rangeStart, horizonDays);
  return {
    from: days[0],
    to: days[days.length - 1],
    days,
    label: horizonApplyLabel(horizon, horizonDays),
  };
}
