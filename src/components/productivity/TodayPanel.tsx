import { useCallback, useEffect, useMemo, useState } from "react";
import { CheckCircle2, Circle, Clock, ListTodo, Loader2, Play, Plus } from "lucide-react";
import {
  completePlannerBlock,
  createPlannerBlock,
  fetchPlannerBlocks,
  startPlannerBlock,
  blockColor,
  type PlannerBlock,
} from "../../api/plannerClient";

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

function fmtTime(iso: string): string {
  return new Date(iso).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

function blocksForDay(blocks: PlannerBlock[], day: Date): PlannerBlock[] {
  return blocks
    .filter((b) => {
      const start = new Date(b.start_at);
      return start >= startOfDay(day) && start <= endOfDay(day);
    })
    .sort((a, b) => new Date(a.start_at).getTime() - new Date(b.start_at).getTime());
}

type Props = {
  day?: Date;
  refreshKey?: number;
  dueReviews?: number;
  onPlannerChange?: () => void;
  compact?: boolean;
};

export function TodayPanel({
  day: dayProp,
  refreshKey = 0,
  dueReviews = 0,
  onPlannerChange,
  compact = false,
}: Props) {
  const day = dayProp ?? new Date();
  const [blocks, setBlocks] = useState<PlannerBlock[]>([]);
  const [loading, setLoading] = useState(true);
  const [quickTitle, setQuickTitle] = useState("");
  const [adding, setAdding] = useState(false);
  const [busyId, setBusyId] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const from = startOfDay(day);
      const to = endOfDay(day);
      const data = await fetchPlannerBlocks(from, to);
      setBlocks(data);
    } finally {
      setLoading(false);
    }
  }, [day.getTime()]);

  useEffect(() => {
    void load();
  }, [load, refreshKey]);

  const todayBlocks = useMemo(() => blocksForDay(blocks, day), [blocks, day.getTime()]);
  const isToday = startOfDay(day).getTime() === startOfDay(new Date()).getTime();
  const dayLabel = isToday
    ? "Today"
    : day.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
  const active = useMemo(
    () => todayBlocks.find((b) => b.status === "in_progress"),
    [todayBlocks],
  );
  const upcoming = useMemo(
    () =>
      todayBlocks.filter(
        (b) => b.status === "scheduled" && new Date(b.start_at) >= new Date(),
      ),
    [todayBlocks],
  );
  const todos = useMemo(
    () =>
      todayBlocks.filter(
        (b) => b.status !== "done" && b.status !== "cancelled" && b.status !== "rolled",
      ),
    [todayBlocks],
  );
  const doneCount = todayBlocks.filter((b) => b.status === "done").length;

  const addQuick = async () => {
    const title = quickTitle.trim();
    if (!title) return;
    setAdding(true);
    try {
      const start = isToday ? new Date() : startOfDay(day);
      if (isToday) {
        start.setMinutes(start.getMinutes() + 5 - (start.getMinutes() % 5));
      } else {
        start.setHours(9, 0, 0, 0);
      }
      await createPlannerBlock({
        title,
        category: "personal",
        start_at: start.toISOString(),
        duration_minutes: 30,
      });
      setQuickTitle("");
      await load();
      onPlannerChange?.();
    } finally {
      setAdding(false);
    }
  };

  const toggleStart = async (block: PlannerBlock) => {
    setBusyId(block.id);
    try {
      if (block.status === "in_progress") {
        await completePlannerBlock(block.id);
      } else if (block.status === "scheduled") {
        await startPlannerBlock(block.id);
      }
      await load();
      onPlannerChange?.();
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className={`rounded-2xl border border-white/10 bg-white/[0.03] ${compact ? "p-4 space-y-3" : "p-5 space-y-4"}`}>
      <div className={`flex flex-wrap items-center gap-3 ${compact ? "justify-between" : "justify-between"}`}>
        <h2 className="font-semibold flex items-center gap-2 text-sm shrink-0">
          <ListTodo size={16} className="text-violet-400" />
          {dayLabel}
        </h2>
        <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
          <span>
            <strong className="text-foreground">{doneCount}</strong> done
          </span>
          <span>
            <strong className="text-foreground">{todos.length}</strong> open
          </span>
          {dueReviews > 0 && (
            <span className="text-amber-400">
              <strong>{dueReviews}</strong> SRS due
            </span>
          )}
        </div>
        {compact && (
          <div className="flex gap-2 flex-1 min-w-[200px] max-w-xl">
            <input
              type="text"
              value={quickTitle}
              onChange={(e) => setQuickTitle(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && void addQuick()}
              placeholder="Quick task…"
              className="flex-1 text-sm px-3 py-1.5 rounded-lg bg-black/30 border border-white/10 placeholder:text-muted-foreground"
            />
            <button
              type="button"
              disabled={adding || !quickTitle.trim()}
              onClick={() => void addQuick()}
              className="px-3 py-1.5 rounded-lg bg-violet-600/80 hover:bg-violet-600 text-sm disabled:opacity-50 flex items-center gap-1 shrink-0"
            >
              {adding ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />}
              Add
            </button>
          </div>
        )}
      </div>

      {active && (
        <div
          className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 flex items-center justify-between gap-2"
          style={{ borderLeftColor: blockColor(active.category, active.color), borderLeftWidth: 3 }}
        >
          <div className="min-w-0">
            <div className="text-[10px] uppercase tracking-wide text-emerald-400">Now</div>
            <div className="font-medium truncate">{active.title}</div>
            <div className="text-xs text-muted-foreground">
              {fmtTime(active.start_at)} · {active.remaining_minutes}m left
            </div>
          </div>
          <button
            type="button"
            disabled={busyId === active.id}
            onClick={() => void toggleStart(active)}
            className="shrink-0 flex items-center gap-1 text-xs px-2 py-1 rounded-lg bg-emerald-600/80 hover:bg-emerald-600 disabled:opacity-50"
          >
            {busyId === active.id ? <Loader2 size={12} className="animate-spin" /> : <CheckCircle2 size={12} />}
            Done
          </button>
        </div>
      )}

      {!compact && (
      <div className="flex gap-2">
        <input
          type="text"
          value={quickTitle}
          onChange={(e) => setQuickTitle(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && void addQuick()}
          placeholder="Quick task — press Enter to add block…"
          className="flex-1 text-sm px-3 py-2 rounded-lg bg-black/30 border border-white/10 placeholder:text-muted-foreground"
        />
        <button
          type="button"
          disabled={adding || !quickTitle.trim()}
          onClick={() => void addQuick()}
          className="px-3 py-2 rounded-lg bg-violet-600/80 hover:bg-violet-600 text-sm disabled:opacity-50 flex items-center gap-1"
        >
          {adding ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />}
          Add
        </button>
      </div>
      )}

      {loading ? (
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-10 rounded-lg bg-white/5 animate-pulse" />
          ))}
        </div>
      ) : todayBlocks.length === 0 ? (
        <p className="text-sm text-muted-foreground py-4 text-center">
          No blocks for {dayLabel.toLowerCase()} — add a task above or import a timetable.
        </p>
      ) : (
        <ul className={`space-y-1 overflow-y-auto pr-1 ${compact ? "max-h-48" : "max-h-64"}`}>
          {todayBlocks.map((block) => {
            const done = block.status === "done";
            const inProg = block.status === "in_progress";
            const isNext = !active && upcoming[0]?.id === block.id;
            return (
              <li
                key={block.id}
                className={`flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm ${
                  inProg ? "bg-emerald-500/10" : isNext ? "bg-violet-500/10" : "hover:bg-white/5"
                }`}
              >
                <button
                  type="button"
                  disabled={busyId === block.id || done}
                  onClick={() => void toggleStart(block)}
                  className="shrink-0 text-muted-foreground hover:text-foreground disabled:opacity-40"
                  title={inProg ? "Mark done" : "Start"}
                >
                  {busyId === block.id ? (
                    <Loader2 size={16} className="animate-spin" />
                  ) : done ? (
                    <CheckCircle2 size={16} className="text-emerald-400" />
                  ) : inProg ? (
                    <CheckCircle2 size={16} className="text-emerald-400" />
                  ) : (
                    <Circle size={16} />
                  )}
                </button>
                <div
                  className="w-1 h-8 rounded-full shrink-0"
                  style={{ backgroundColor: blockColor(block.category, block.color) }}
                />
                <div className="flex-1 min-w-0">
                  <div className={`truncate ${done ? "line-through text-muted-foreground" : ""}`}>
                    {block.title}
                    {isNext && <span className="ml-1 text-[10px] text-violet-400">next</span>}
                  </div>
                  <div className="text-[11px] text-muted-foreground flex items-center gap-1">
                    <Clock size={10} />
                    {fmtTime(block.start_at)} · {block.category}
                  </div>
                </div>
                {!done && block.status === "scheduled" && (
                  <button
                    type="button"
                    disabled={busyId === block.id}
                    onClick={() => void toggleStart(block)}
                    className="text-[10px] px-2 py-0.5 rounded border border-white/10 hover:bg-white/10"
                  >
                    <Play size={10} className="inline" /> Start
                  </button>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
