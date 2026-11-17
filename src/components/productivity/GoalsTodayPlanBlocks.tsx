import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  CalendarDays,
  Check,
  ChevronDown,
  ChevronUp,
  ClipboardCopy,
  FileUp,
  GripVertical,
  Loader2,
  Minus,
  Plus,
  RefreshCw,
  Trash2,
  X,
} from "lucide-react";
import {
  fetchPlannerBlocks,
  fetchRoutines,
  type PlannerBlock,
  type PlannerRoutine,
  type StudyTask,
} from "../../api/plannerClient";
import { fetchDayLoopMirror } from "../../api/focusMirrors";
import { cn } from "../../app/components/ui/utils";
import {
  availableFocusGapHours,
  isStudyFocusCategory,
  studyMinutesFromBlocks,
  syncStudyHoursToFocusGoal,
} from "./fillFocusStudyGaps";

type SideTodo = {
  id: string;
  title: string;
  done: boolean;
  minutes: number;
};

function blockMinutes(b: PlannerBlock): number {
  const a = new Date(b.start_at).getTime();
  const e = new Date(b.end_at).getTime();
  if (!Number.isFinite(a) || !Number.isFinite(e) || e <= a) return Math.max(0, b.planned_minutes || 0);
  return Math.max(0, Math.round((e - a) / 60_000));
}

function newTodoId(): string {
  return `g-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`;
}

/** Canonical AI format: one `Title | minutes` per line (optional header). */
export const FOCUS_TASK_IMPORT_CANONICAL = `# calt-focus-tasks
Read chapter 3 | 45
Write notes | 30
Review flashcards | 15`;

const IMPORT_PLACEHOLDER = `# calt-focus-tasks
Read chapter 3 | 45
Write notes | 30
Review flashcards`;

/** Build a clipboard-ready prompt for ChatGPT/Claude/etc. */
export function buildFocusTaskAiPrompt(goalMinutes: number): string {
  const goal =
    Number.isFinite(goalMinutes) && goalMinutes > 0
      ? Math.round(goalMinutes)
      : 0;
  const goalLine =
    goal > 0
      ? `Today's focus goal is about ${goal} minutes. Sum task minutes to roughly ${goal}.`
      : `Pick a sensible total (e.g. 90–180 minutes) and sum task minutes to match.`;
  return `Generate a daily focus task list for CALT Focus.

${goalLine}

Reply with ONLY the task list — no intro, bullets, or markdown fences. Use this exact format:

# calt-focus-tasks
Title | minutes

Rules:
- One task per line after the header
- minutes = integer (optional trailing m); omit minutes to default to 25
- Pipe separator required: Title | minutes
- Keep titles short and concrete

Example:
${FOCUS_TASK_IMPORT_CANONICAL}`;
}

/** Parse pasted import text into titled tasks with minutes. */
export function parseFocusTaskImport(raw: string): { title: string; minutes: number }[] {
  const lines = raw
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter((l) => l && !l.startsWith("#"));
  const out: { title: string; minutes: number }[] = [];
  let skipRest = false;
  for (const line of lines) {
    // Prompt paste: stop at the embedded Example block
    if (/^example:/i.test(line)) {
      skipRest = true;
      continue;
    }
    if (skipRest) continue;

    // Skip format-spec / prompt lines accidentally pasted with the list
    if (
      /^examples?:$/i.test(line) ||
      /^one task per line/i.test(line) ||
      /^title\s*\|\s*minutes$/i.test(line) ||
      /^rules?:$/i.test(line) ||
      /^generate a daily focus/i.test(line) ||
      /^today'?s focus goal/i.test(line) ||
      /^reply with only/i.test(line) ||
      /^pick a sensible total/i.test(line) ||
      /^- (one task|minutes|pipe|keep titles)/i.test(line)
    ) {
      continue;
    }

    let title = line;
    let minutes = 25;

    // "1. Title …" / "1) Title" (tolerant)
    title = title.replace(/^\d+[.)]\s+/, "");

    // Canonical + tolerant: "… | 45" / "… | 45m" / "…, 45" / "… - 60m" / "… 45m" / "… 30"
    const pipe = title.match(/^(.*?)\s*[|,—–-]\s*(\d{1,3})\s*m?\s*$/i);
    if (pipe) {
      title = pipe[1].trim();
      minutes = Number(pipe[2]);
    } else {
      // Prefer explicit "45m"; bare trailing digits only if a plausible duration (≥5)
      // so titles like "Chapter 3" stay intact.
      const trailM = title.match(/^(.*?)\s+(\d{1,3})\s*m\s*$/i);
      if (trailM) {
        title = trailM[1].trim();
        minutes = Number(trailM[2]);
      } else {
        const trailBare = title.match(/^(.*?)\s+(\d{1,3})\s*$/);
        if (trailBare) {
          const n = Number(trailBare[2]);
          if (n >= 5 && n <= 480) {
            title = trailBare[1].trim();
            minutes = n;
          }
        }
      }
    }

    title = title.replace(/^[-*•]\s+/, "").trim();
    if (!title) continue;
    if (!Number.isFinite(minutes) || minutes < 5) minutes = 25;
    minutes = Math.max(5, Math.min(480, Math.round(minutes)));
    out.push({ title, minutes });
  }
  return out;
}

type Props = {
  focusHours: number;
  onFocusHoursChange: (hours: number) => void;
  studyTasks?: StudyTask[];
  refreshKey?: number;
  onChanged?: () => void;
  onOpenCalendar?: () => void;
  /** Side todos folded into this card */
  extraGoals: SideTodo[];
  onExtraGoalsChange: (next: SideTodo[]) => void;
  effectiveHours: number;
};

/**
 * Daily focus goal + numbered focus tasks (allocator sequence).
 * Study/work calendar blocks are managed on Calendar / via Allocate — not listed here.
 */
export function GoalsTodayPlanBlocks({
  focusHours,
  onFocusHoursChange,
  studyTasks,
  refreshKey = 0,
  onChanged,
  onOpenCalendar,
  extraGoals,
  onExtraGoalsChange,
  effectiveHours,
}: Props) {
  const [blocks, setBlocks] = useState<PlannerBlock[]>([]);
  const [routines, setRoutines] = useState<PlannerRoutine[]>([]);
  const [loading, setLoading] = useState(true);
  const [applying, setApplying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [draftTodo, setDraftTodo] = useState("");
  const [importOpen, setImportOpen] = useState(false);
  const [importText, setImportText] = useState("");
  const [importMode, setImportMode] = useState<"append" | "replace">("append");
  const [promptCopied, setPromptCopied] = useState(false);
  const [wakeHm, setWakeHm] = useState<string | null>(null);
  const [bedtimeHm, setBedtimeHm] = useState<string | null>(null);
  const [dragId, setDragId] = useState<string | null>(null);
  const syncingRef = useRef(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const day = new Date();
      const start = new Date(day);
      start.setHours(0, 0, 0, 0);
      const end = new Date(day);
      end.setHours(23, 59, 59, 999);
      const [list, routineRows] = await Promise.all([
        fetchPlannerBlocks(start, end),
        fetchRoutines().catch(() => [] as PlannerRoutine[]),
      ]);
      setBlocks(
        list
          .filter((b) => b.status !== "cancelled" && b.status !== "rolled")
          .sort((a, b) => new Date(a.start_at).getTime() - new Date(b.start_at).getTime()),
      );
      setRoutines(Array.isArray(routineRows) ? routineRows : []);
      try {
        const loop = await fetchDayLoopMirror();
        setWakeHm(typeof loop?.wake_hm === "string" ? loop.wake_hm : null);
        setBedtimeHm(typeof loop?.bedtime_hm === "string" ? loop.bedtime_hm : null);
      } catch {
        /* sleep clocks optional */
      }
    } catch (e: unknown) {
      setBlocks([]);
      setRoutines([]);
      setError(e instanceof Error ? e.message : "Could not load plan blocks");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load, refreshKey]);

  /** Work/study only — routines stay on Calendar / Routines, not here. */
  const focusBlocks = useMemo(
    () => blocks.filter((b) => isStudyFocusCategory(b.category || "")),
    [blocks],
  );

  /** Max focus: waking window (sleep clocks) minus routines, else routine-gap fallback. */
  const availableHours = useMemo(
    () => availableFocusGapHours({ blocks, routines, wakeHm, bedtimeHm }),
    [blocks, routines, wakeHm, bedtimeHm],
  );
  const hasRoutineCap = availableHours > 0;

  const goalMins = Math.round(Math.max(0, focusHours) * 60);
  const progressPct =
    focusHours > 0 ? Math.min(100, Math.round((effectiveHours / focusHours) * 100)) : 0;
  const met = focusHours > 0 && effectiveHours >= focusHours;

  const clampFocusHours = useCallback(
    (hours: number) => {
      const ceiling = hasRoutineCap ? availableHours : 16;
      const next = Math.round(Math.max(0.5, hours) * 10) / 10;
      return Math.min(ceiling, next);
    },
    [availableHours, hasRoutineCap],
  );

  const bumpFocus = (dir: 1 | -1) => {
    const next = Math.round((focusHours + dir * 0.5) * 10) / 10;
    onFocusHoursChange(clampFocusHours(next));
  };

  // Keep stored goal ≤ routine-gap capacity once today's routines are known.
  useEffect(() => {
    if (loading || !hasRoutineCap) return;
    if (focusHours <= availableHours + 0.05) return;
    onFocusHoursChange(availableHours);
  }, [loading, hasRoutineCap, availableHours, focusHours, onFocusHoursChange]);

  const runSync = useCallback(async () => {
    if (syncingRef.current) return;
    syncingRef.current = true;
    setApplying(true);
    setError(null);
    setStatus(null);
    try {
      // No routine apply — allocator only fills study/work toward the focus goal.
      const day = new Date();
      const start = new Date(day);
      start.setHours(0, 0, 0, 0);
      const end = new Date(day);
      end.setHours(23, 59, 59, 999);
      const latest = await fetchPlannerBlocks(start, end);
      let wakeHm: string | null = null;
      let bedtimeHm: string | null = null;
      try {
        const loop = await fetchDayLoopMirror();
        wakeHm = typeof loop?.wake_hm === "string" ? loop.wake_hm : null;
        bedtimeHm = typeof loop?.bedtime_hm === "string" ? loop.bedtime_hm : null;
      } catch {
        /* defaults */
      }
      // Prefer numbered focus tasks (open todos with minutes) as allocator sequence.
      const openTasks = extraGoals.filter((g) => !g.done && g.title.trim());
      const seqTasks: StudyTask[] =
        openTasks.length > 0
          ? openTasks.map((g, i) => ({
              id: g.id || `seq-${i}`,
              title: g.title.trim(),
              minutes: Math.max(5, Math.min(480, g.minutes || 25)),
              allowHosts: [],
              blockCategories: [],
            }))
          : focusBlocks.length > 0
            ? focusBlocks.map((b, i) => ({
                id: `seq-${b.id}`,
                title: (b.title || `Block ${i + 1}`).trim(),
                minutes: Math.max(25, blockMinutes(b)),
                allowHosts: [],
                blockCategories: [],
              }))
            : studyTasks || [];
      const fill = await syncStudyHoursToFocusGoal({
        focusHours,
        blocks: latest,
        wakeHm,
        bedtimeHm,
        studyTasks: seqTasks,
      });
      await load();
      onChanged?.();

      const bits: string[] = [];
      if (fill.created > 0) {
        bits.push(
          `${fill.created} block${fill.created === 1 ? "" : "s"} (+${(fill.minutesAdded / 60).toFixed(1)}h)`,
        );
      }
      if (fill.deleted > 0) {
        bits.push(`trimmed ${fill.deleted} (+${(fill.minutesRemoved / 60).toFixed(1)}h)`);
      }
      if (bits.length === 0) {
        const have = studyMinutesFromBlocks(latest);
        const goal = Math.round(Math.max(0, focusHours) * 60);
        if (Math.abs(goal - have) < 25) setStatus("Study hours match today's focus goal.");
        else if (have > goal)
          setStatus(`${((have - goal) / 60).toFixed(1)}h over — trim a block or lower the goal.`);
        else setStatus("No free gaps left — clear a Calendar slot or lower a routine there.");
      } else {
        const still =
          fill.shortfallAfter >= 25 ? ` · still ${(fill.shortfallAfter / 60).toFixed(1)}h short` : "";
        setStatus(`Allocated ${bits.join(" · ")}${still}.`);
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Allocate failed");
    } finally {
      setApplying(false);
      syncingRef.current = false;
    }
  }, [focusHours, studyTasks, focusBlocks, extraGoals, load, onChanged]);

  const addTodo = () => {
    const title = draftTodo.trim();
    if (!title) return;
    const open = extraGoals.filter((g) => !g.done);
    const defaultMin =
      open.length === 0
        ? Math.max(25, Math.round((focusHours * 60) / 2 / 5) * 5)
        : 25;
    onExtraGoalsChange([
      ...extraGoals,
      {
        id: newTodoId(),
        title,
        done: false,
        minutes: defaultMin,
      },
    ]);
    setDraftTodo("");
  };

  const applyImport = () => {
    const parsed = parseFocusTaskImport(importText);
    if (!parsed.length) {
      setError("No tasks found — paste lines like: Title | minutes");
      return;
    }
    const mapped = parsed.map((p) => ({
      id: newTodoId(),
      title: p.title,
      done: false,
      minutes: p.minutes,
    }));
    onExtraGoalsChange(importMode === "replace" ? mapped : [...extraGoals, ...mapped]);
    setImportText("");
    setImportOpen(false);
    setError(null);
    setStatus(
      `Imported ${mapped.length} task${mapped.length === 1 ? "" : "s"} (${importMode === "replace" ? "replaced list" : "appended"}).`,
    );
  };

  const copyAiPrompt = async () => {
    const text = buildFocusTaskAiPrompt(goalMins);
    try {
      await navigator.clipboard.writeText(text);
      setPromptCopied(true);
      setError(null);
      window.setTimeout(() => setPromptCopied(false), 2000);
    } catch {
      setError("Could not copy prompt — select and copy manually.");
    }
  };

  const importPreviewCount = useMemo(
    () => (importOpen ? parseFocusTaskImport(importText).length : 0),
    [importOpen, importText],
  );
  const openTodos = useMemo(
    () => extraGoals.filter((g) => !g.done && g.title.trim()),
    [extraGoals],
  );
  const todoMins = useMemo(
    () => openTodos.reduce((n, g) => n + Math.max(5, g.minutes || 25), 0),
    [openTodos],
  );
  const goalMinTotal = Math.round(Math.max(0, focusHours) * 60);
  const todoPct = goalMinTotal > 0 ? Math.min(100, Math.round((todoMins / goalMinTotal) * 100)) : 0;

  const moveTodo = (index: number, dir: -1 | 1) => {
    const next = index + dir;
    if (next < 0 || next >= extraGoals.length) return;
    const copy = [...extraGoals];
    const tmp = copy[index];
    copy[index] = copy[next];
    copy[next] = tmp;
    onExtraGoalsChange(copy);
  };

  const reorderTodo = (fromId: string, toId: string) => {
    if (fromId === toId) return;
    const from = extraGoals.findIndex((g) => g.id === fromId);
    const to = extraGoals.findIndex((g) => g.id === toId);
    if (from < 0 || to < 0) return;
    const copy = [...extraGoals];
    const [item] = copy.splice(from, 1);
    copy.splice(to, 0, item);
    onExtraGoalsChange(copy);
  };

  const formatSleepClock = (hm: string) => {
    const m = /^(\d{1,2}):(\d{2})/.exec(hm.trim());
    if (!m) return hm;
    const h24 = Number(m[1]);
    const min = m[2];
    const am = h24 < 12;
    let h12 = h24 % 12;
    if (h12 === 0) h12 = 12;
    return `${h12}:${min} ${am ? "AM" : "PM"}`;
  };

  const bumpTodoMinutes = (id: string, dir: 1 | -1) => {
    onExtraGoalsChange(
      extraGoals.map((g) => {
        if (g.id !== id) return g;
        const cur = Math.max(5, g.minutes || 25);
        return { ...g, minutes: Math.max(5, Math.min(480, cur + dir * 5)) };
      }),
    );
  };

  const splitGoalEvenly = () => {
    const open = extraGoals.filter((g) => !g.done && g.title.trim());
    if (!open.length || goalMinTotal <= 0) return;
    const base = Math.max(5, Math.floor(goalMinTotal / open.length / 5) * 5);
    let remain = goalMinTotal - base * open.length;
    const nextMins = new Map<string, number>();
    open.forEach((g, i) => {
      let m = base;
      if (remain >= 5) {
        m += 5;
        remain -= 5;
      } else if (i === open.length - 1 && remain > 0) {
        m += remain;
      }
      nextMins.set(g.id, Math.max(5, Math.min(480, m)));
    });
    onExtraGoalsChange(
      extraGoals.map((g) => (nextMins.has(g.id) ? { ...g, minutes: nextMins.get(g.id)! } : g)),
    );
  };

  return (
    <section className="goals-focus-plan gloss-panel rounded-2xl border border-border/40 overflow-hidden">
      {/* Adjustable daily focus */}
      <div className="border-b border-white/8 bg-black/25 px-3.5 py-3 space-y-2">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground">Daily focus</p>
            <div
              className="mt-0.5 flex items-baseline gap-1.5"
              title={
                hasRoutineCap
                  ? `Goal / free time between first and last routine (${availableHours.toFixed(1)}h gaps)`
                  : "Daily focus goal hours"
              }
            >
              <span className="text-3xl font-semibold tabular-nums tracking-tight text-emerald-100">
                {Number(focusHours).toFixed(1)}
              </span>
              {hasRoutineCap ? (
                <>
                  <span className="text-xl font-medium text-muted-foreground/70" aria-hidden>
                    /
                  </span>
                  <span className="text-3xl font-semibold tabular-nums tracking-tight text-sky-200/90">
                    {availableHours.toFixed(1)}
                  </span>
                </>
              ) : null}
              <span className="text-sm text-muted-foreground">hours</span>
            </div>
            {wakeHm && bedtimeHm ? (
              <p className="mt-0.5 text-[10px] text-muted-foreground/85">
                Wake {formatSleepClock(wakeHm)} · Bed {formatSleepClock(bedtimeHm)}
                <span className="text-muted-foreground/60"> · edit on Routines</span>
              </p>
            ) : null}
          </div>
          <div className="flex items-center gap-2">
            <div className="flex flex-col rounded-lg border border-white/12 overflow-hidden" aria-label="Adjust daily focus hours">
              <button
                type="button"
                onClick={() => bumpFocus(1)}
                disabled={hasRoutineCap && focusHours >= availableHours - 0.05}
                className="px-2 py-1 hover:bg-white/5 text-muted-foreground hover:text-foreground disabled:opacity-35"
                aria-label="Increase daily focus"
              >
                <ChevronUp size={14} />
              </button>
              <button
                type="button"
                onClick={() => bumpFocus(-1)}
                disabled={focusHours <= 0.5}
                className="px-2 py-1 border-t border-white/10 hover:bg-white/5 text-muted-foreground hover:text-foreground disabled:opacity-35"
                aria-label="Decrease daily focus"
              >
                <ChevronDown size={14} />
              </button>
            </div>
            <button
              type="button"
              disabled={applying || loading}
              onClick={() => void runSync()}
              title="Allocate study/work blocks to match focus hours (routines untouched)"
              className="inline-flex items-center gap-1 rounded-lg bg-amber-600/80 hover:bg-amber-600 px-2.5 py-1.5 text-[11px] font-medium text-amber-50 disabled:opacity-50"
            >
              {applying ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
              Allocate
            </button>
            <button
              type="button"
              onClick={() => {
                if (onOpenCalendar) onOpenCalendar();
                else window.location.hash = "#/productivity?tab=calendar";
              }}
              className="inline-flex items-center gap-1 text-[11px] text-sky-300/90 hover:text-sky-200"
            >
              <CalendarDays size={12} /> Calendar
            </button>
          </div>
        </div>
        <div className="h-1.5 rounded-full bg-white/8 overflow-hidden" aria-hidden>
          <div
            className={cn("h-full rounded-full transition-[width]", met ? "bg-emerald-400" : "bg-sky-400")}
            style={{ width: `${progressPct}%` }}
          />
        </div>
      </div>

      {/* Numbered focus tasks — subdivide daily goal for the allocator */}
      <div className="px-3.5 py-3 space-y-2.5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="min-w-0">
            <h4 className="text-xs font-semibold text-foreground">Focus tasks</h4>
            <p className="text-[10px] text-muted-foreground">
              # sequence · minutes subdivide {focusHours}h · Allocate uses this order
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] tabular-nums text-muted-foreground">
              {todoMins}m / {goalMinTotal}m
            </span>
            <button
              type="button"
              disabled={openTodos.length === 0 || goalMinTotal <= 0}
              onClick={splitGoalEvenly}
              className="rounded-md border border-white/12 px-2 py-0.5 text-[10px] text-muted-foreground hover:text-foreground hover:bg-white/5 disabled:opacity-40"
              title="Split daily focus minutes evenly across open tasks"
            >
              Split evenly
            </button>
            <button
              type="button"
              onClick={() => {
                setImportOpen((v) => !v);
                setError(null);
              }}
              className={cn(
                "inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[10px]",
                importOpen
                  ? "border-sky-400/40 bg-sky-500/15 text-sky-100"
                  : "border-white/12 text-muted-foreground hover:text-foreground hover:bg-white/5",
              )}
            >
              <FileUp size={11} /> Import
            </button>
          </div>
        </div>

        {importOpen ? (
          <div className="rounded-xl border border-sky-400/25 bg-sky-500/[0.06] p-2.5 space-y-2">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0 space-y-1">
                <p className="text-[10px] text-sky-100/90 font-medium">
                  AI format — one task per line
                </p>
                <pre className="text-[10px] font-mono leading-relaxed text-muted-foreground whitespace-pre-wrap">{`# calt-focus-tasks
Title | minutes`}</pre>
                <p className="text-[9px] text-muted-foreground/80">
                  {goalMins > 0
                    ? `Minutes optional (default 25). Paste AI output below · goal ${goalMins}m.`
                    : "Minutes optional (default 25). Paste AI output below."}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setImportOpen(false)}
                className="shrink-0 p-1 text-muted-foreground hover:text-foreground"
                aria-label="Close import"
              >
                <X size={12} />
              </button>
            </div>
            <textarea
              value={importText}
              onChange={(e) => setImportText(e.target.value)}
              rows={5}
              placeholder={IMPORT_PLACEHOLDER}
              spellCheck={false}
              className="w-full rounded-lg border border-white/10 bg-black/40 px-2.5 py-2 text-[11px] font-mono text-foreground placeholder:text-muted-foreground/60"
            />
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={() => void copyAiPrompt()}
                className="inline-flex items-center gap-1 rounded-lg border border-sky-400/30 bg-sky-500/10 px-2 py-1 text-[10px] text-sky-100 hover:bg-sky-500/20"
                title="Copy a prompt + format for ChatGPT / Claude"
              >
                {promptCopied ? <Check size={11} /> : <ClipboardCopy size={11} />}
                {promptCopied ? "Copied" : "Copy prompt"}
              </button>
              <div className="flex rounded-lg border border-white/12 overflow-hidden text-[10px]">
                <button
                  type="button"
                  onClick={() => setImportMode("append")}
                  className={cn(
                    "px-2 py-1",
                    importMode === "append"
                      ? "bg-white/10 text-foreground"
                      : "text-muted-foreground hover:bg-white/5",
                  )}
                >
                  Append
                </button>
                <button
                  type="button"
                  onClick={() => setImportMode("replace")}
                  className={cn(
                    "px-2 py-1 border-l border-white/10",
                    importMode === "replace"
                      ? "bg-white/10 text-foreground"
                      : "text-muted-foreground hover:bg-white/5",
                  )}
                >
                  Replace all
                </button>
              </div>
              <button
                type="button"
                disabled={!importText.trim()}
                onClick={applyImport}
                className="inline-flex items-center gap-1 rounded-lg bg-sky-600/80 hover:bg-sky-600 px-2.5 py-1 text-[11px] font-medium text-sky-50 disabled:opacity-40"
              >
                <FileUp size={11} />
                {importPreviewCount > 0
                  ? ` Import ${importPreviewCount} task${importPreviewCount === 1 ? "" : "s"}`
                  : " Import"}
              </button>
            </div>
          </div>
        ) : null}

        <div className="h-1.5 rounded-full bg-white/8 overflow-hidden" aria-hidden>
          <div
            className={cn(
              "h-full rounded-full transition-[width]",
              todoPct >= 100 ? "bg-emerald-400" : todoPct >= 70 ? "bg-sky-400" : "bg-amber-400/80",
            )}
            style={{ width: `${todoPct}%` }}
          />
        </div>

        <ul className="space-y-1.5">
          {extraGoals.length === 0 ? (
            <li className="text-[11px] text-muted-foreground py-1">
              Add numbered tasks below, set each timer, then Allocate onto the calendar.
            </li>
          ) : (
            extraGoals.map((g, i) => {
              const mins = Math.max(5, g.minutes || 25);
              return (
                <li
                  key={g.id}
                  onDragOver={(e) => {
                    if (!dragId) return;
                    e.preventDefault();
                    e.dataTransfer.dropEffect = "move";
                  }}
                  onDrop={(e) => {
                    e.preventDefault();
                    const from = e.dataTransfer.getData("text/plain") || dragId;
                    if (from) reorderTodo(from, g.id);
                    setDragId(null);
                  }}
                  className={cn(
                    "rounded-xl border border-white/8 bg-black/30 px-2 py-1.5 flex flex-wrap items-center gap-2",
                    g.done && "opacity-55",
                    dragId === g.id && "opacity-70 ring-1 ring-sky-400/40",
                  )}
                >
                  <span
                    draggable
                    onDragStart={(e) => {
                      setDragId(g.id);
                      e.dataTransfer.effectAllowed = "move";
                      e.dataTransfer.setData("text/plain", g.id);
                    }}
                    onDragEnd={() => setDragId(null)}
                    className="shrink-0 cursor-grab active:cursor-grabbing p-0.5 text-muted-foreground/70 hover:text-foreground"
                    title="Drag to reorder"
                    aria-label="Drag to reorder"
                  >
                    <GripVertical size={14} />
                  </span>
                  <div className="flex flex-col shrink-0">
                    <button
                      type="button"
                      disabled={i === 0}
                      onClick={() => moveTodo(i, -1)}
                      className="p-0.5 text-muted-foreground hover:text-foreground disabled:opacity-30"
                      aria-label="Move earlier in sequence"
                    >
                      <ChevronUp size={12} />
                    </button>
                    <button
                      type="button"
                      disabled={i >= extraGoals.length - 1}
                      onClick={() => moveTodo(i, 1)}
                      className="p-0.5 text-muted-foreground hover:text-foreground disabled:opacity-30"
                      aria-label="Move later in sequence"
                    >
                      <ChevronDown size={12} />
                    </button>
                  </div>
                  <span
                    className="flex size-6 shrink-0 items-center justify-center rounded-md bg-sky-500/20 text-[11px] font-semibold tabular-nums text-sky-100"
                    title={`Sequence ${i + 1}`}
                  >
                    {i + 1}
                  </span>
                  <button
                    type="button"
                    onClick={() =>
                      onExtraGoalsChange(
                        extraGoals.map((x) => (x.id === g.id ? { ...x, done: !x.done } : x)),
                      )
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
                      onExtraGoalsChange(
                        extraGoals.map((x) =>
                          x.id === g.id ? { ...x, title: e.target.value } : x,
                        ),
                      )
                    }
                    className={cn(
                      "min-w-[7rem] flex-1 rounded-md border border-transparent bg-transparent px-1.5 py-1 text-[12px] text-foreground focus:border-white/15 focus:bg-black/40",
                      g.done && "line-through text-muted-foreground",
                    )}
                    aria-label={`Task ${i + 1} title`}
                    placeholder="Task name"
                  />
                  <div
                    className="inline-flex items-center gap-0.5 rounded-lg border border-white/12 bg-black/35 shrink-0"
                    title="Minutes from daily focus goal"
                  >
                    <button
                      type="button"
                      disabled={g.done || mins <= 5}
                      onClick={() => bumpTodoMinutes(g.id, -1)}
                      className="p-1.5 text-muted-foreground hover:text-foreground disabled:opacity-30"
                      aria-label="Minus 5 minutes"
                    >
                      <Minus size={12} />
                    </button>
                    <span className="min-w-[2.75rem] text-center text-[11px] font-medium tabular-nums">
                      {mins}m
                    </span>
                    <button
                      type="button"
                      disabled={g.done || mins >= 480}
                      onClick={() => bumpTodoMinutes(g.id, 1)}
                      className="p-1.5 text-muted-foreground hover:text-foreground disabled:opacity-30"
                      aria-label="Plus 5 minutes"
                    >
                      <Plus size={12} />
                    </button>
                  </div>
                  <button
                    type="button"
                    onClick={() => onExtraGoalsChange(extraGoals.filter((x) => x.id !== g.id))}
                    className="p-1.5 text-muted-foreground hover:text-rose-300"
                    aria-label="Remove task"
                  >
                    <Trash2 size={12} />
                  </button>
                </li>
              );
            })
          )}
        </ul>
        <div className="flex gap-2">
          <input
            value={draftTodo}
            onChange={(e) => setDraftTodo(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                addTodo();
              }
            }}
            placeholder="Task name…"
            className="flex-1 rounded-lg border border-white/10 bg-black/25 px-2.5 py-1.5 text-xs text-foreground"
          />
          <button
            type="button"
            onClick={addTodo}
            disabled={!draftTodo.trim()}
            className="inline-flex items-center gap-1 rounded-lg border border-white/12 px-2.5 py-1.5 text-xs text-muted-foreground hover:text-foreground hover:bg-white/5 disabled:opacity-40"
          >
            <Plus size={12} /> Add
          </button>
        </div>
      </div>

      {status ? (
        <p className="border-t border-white/8 px-3.5 py-2 text-[11px] text-emerald-200/90">{status}</p>
      ) : null}
      {error ? (
        <p className="border-t border-white/8 px-3.5 py-2 text-[11px] text-rose-300">{error}</p>
      ) : null}
    </section>
  );
}
