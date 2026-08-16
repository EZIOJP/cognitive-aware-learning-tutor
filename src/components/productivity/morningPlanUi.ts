/**
 * Pure labels for morning Plan tab + Settings — keep UI copy consistent.
 */

export type PlanWindowPhase =
  | "awaiting_bible"
  | "before_start"
  | "open"
  | "after_eod"
  | string;

export type PlanConfirmUi = {
  phase: PlanWindowPhase;
  windowOpen: boolean;
  windowLabel: string;
  ctaLabel: string;
  ctaDisabled: boolean;
  hint: string;
};

export function planConfirmUi(opts: {
  next?: string | null;
  planDone?: boolean;
  phase?: PlanWindowPhase | null;
  confirmAvailable?: boolean | null;
  startClock?: string | null;
  endLabel?: string | null;
  eodHhmm?: string | null;
  blocksToday?: number;
  planPoints?: number;
  serverHint?: string | null;
}): PlanConfirmUi {
  const phase = (opts.phase || "open") as PlanWindowPhase;
  const points = opts.planPoints ?? 10;
  const blocks = opts.blocksToday ?? 0;
  const start = opts.startClock || "05:00";
  const endLabel = opts.endLabel || "midnight";
  const eod = opts.eodHhmm || "23:59";

  if (opts.planDone) {
    return {
      phase,
      windowOpen: false,
      windowLabel: "Confirmed",
      ctaLabel: "Plan confirmed",
      ctaDisabled: true,
      hint: opts.serverHint || "Morning plan step is done for today.",
    };
  }

  if (phase === "before_start") {
    // Soft planning: 05:00 is a hint only — never lock Confirm on the clock.
    return {
      phase,
      windowOpen: true,
      windowLabel: `Open · usual ${start}`,
      ctaLabel: `Confirm today’s plan (+${points})`,
      ctaDisabled: false,
      hint:
        opts.serverHint && !/opens at|plan opens/i.test(opts.serverHint)
          ? opts.serverHint
          : `Edit and confirm anytime — ${start} is only the usual morning start, not a lock.`,
    };
  }

  if (phase === "after_eod") {
    return {
      phase,
      windowOpen: true,
      windowLabel: `Open · past ${eod}`,
      ctaLabel: `Confirm today’s plan (+${points})`,
      ctaDisabled: false,
      hint:
        opts.serverHint && !/ended|no longer required|closed/i.test(opts.serverHint)
          ? opts.serverHint
          : `Past usual end (${eod}). Soft-land won’t force plan — you can still confirm.`,
    };
  }

  if (phase === "awaiting_bible") {
    return {
      phase,
      windowOpen: false,
      windowLabel: "Waiting on Bible",
      ctaLabel: "Finish Bible first",
      ctaDisabled: true,
      hint: opts.serverHint || "Finish today’s Bible chapter before confirming the plan.",
    };
  }

  const available =
    opts.confirmAvailable !== false &&
    (opts.next === "plan" || opts.next === "open" || !opts.next);
  return {
    phase: phase === "open" ? "open" : phase,
    windowOpen: available,
    windowLabel: available ? `Open · until ${endLabel}` : "Review plan",
    ctaLabel: available ? `Confirm today’s plan (+${points})` : `Confirm today’s plan (+${points})`,
    ctaDisabled: false,
    hint:
      opts.serverHint && !/opens at|plan opens/i.test(opts.serverHint)
        ? opts.serverHint
        : `Review goals & blocks (${blocks} today), then confirm anytime (+${points}).`,
  };
}

/** Short study vs free browser-mode line for Plan tab. */
export function browserModeHint(opts: {
  mode?: string | null;
  modeLabel?: string | null;
  freeAfter?: string | null;
  note?: string | null;
}): { label: string; tone: "strict" | "free"; detail: string } | null {
  const mode = (opts.mode || "").toLowerCase();
  if (!mode && !opts.modeLabel) return null;
  const label = opts.modeLabel || mode.toUpperCase() || "—";
  const strict = ["bible", "planning", "study"].includes(mode);
  const freeAfter = opts.freeAfter || "21:00";
  if (strict) {
    return {
      label,
      tone: "strict",
      detail:
        mode === "planning"
          ? "Planning mode — confirm today’s blocks, then daytime defaults to STUDY."
          : `STUDY blocks YouTube/Netflix; Scaler/Colab allowed. Free after ${freeAfter} or in break blocks.`,
    };
  }
  return {
    label,
    tone: "free",
    detail: opts.note || `Free window (distractions still filtered). Evening free from ${freeAfter}.`,
  };
}

export function formatBlockClock(iso: string): string {
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "—";
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "—";
  }
}
