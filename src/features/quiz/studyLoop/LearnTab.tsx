import { useEffect, useState } from "react";
import { Loader2, Play } from "lucide-react";
import { toast } from "sonner";
import { Button } from "../../../app/components/ui/button";
import {
  fetchStudyLoopToday,
  startStudyLoopToday,
  type StudyLoopTag,
} from "../../../api/globalQuizClient";
import type { DueReviewItem } from "../types";
import { ActiveBoard } from "./ActiveBoard";
import type { KindFilter } from "./dailyLearnKinds";
import { ACTIVE_TAG_CAP } from "./activeTagsStorage";
import { dueIntersectsActive } from "./dueActiveFilter";

type Props = {
  tags: StudyLoopTag[];
  activeIds: string[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onActivate: (id: string) => void;
  onPark: (id: string) => void;
  activeKind: KindFilter;
  backlogKind: KindFilter;
  onActiveKind: (k: KindFilter) => void;
  onBacklogKind: (k: KindFilter) => void;
  capHint: boolean;
  due: DueReviewItem[];
  showFsrs: boolean;
  busy: boolean;
  onStartActiveFocus: () => void;
  onFocusSelected: () => void;
  onReviewDue: () => void;
  onReviewItem: (item: DueReviewItem) => void;
  onStartPractice: (quizSessionId: string) => void;
  onOpenNotes: (tagId: string) => void;
};

export function LearnTab({
  tags,
  activeIds,
  selectedId,
  onSelect,
  onActivate,
  onPark,
  activeKind,
  backlogKind,
  onActiveKind,
  onBacklogKind,
  capHint,
  due,
  showFsrs,
  busy,
  onStartActiveFocus,
  onFocusSelected,
  onReviewDue,
  onReviewItem,
  onStartPractice,
  onOpenNotes,
}: Props) {
  const byId = new Map(tags.map((t) => [String(t.id), t]));
  const active = activeIds.map((id) => byId.get(id)).filter(Boolean) as StudyLoopTag[];
  const activeSet = new Set(activeIds);
  const backlog = tags.filter((t) => !activeSet.has(String(t.id)));

  const activeDue =
    activeIds.length > 0
      ? due.filter((item) => dueIntersectsActive(item, activeIds))
      : due;
  const fsrsReady = activeDue.length;

  const activeWithDue = active.filter((t) => Number(t.due_count || 0) > 0).length;

  const [todayBusy, setTodayBusy] = useState(false);
  const [today, setToday] = useState<{
    day: string;
    tags: string[];
    state: string;
    steps?: Array<{ tag?: string; kind?: string; label?: string }>;
  } | null>(null);

  useEffect(() => {
    void fetchStudyLoopToday()
      .then((t) =>
        setToday({
          day: t.day,
          tags: t.tags || [],
          state: t.state,
          steps: (t.steps || []) as Array<{ tag?: string; kind?: string; label?: string }>,
        })
      )
      .catch(() => setToday(null));
  }, []);

  const startDaily = async () => {
    setTodayBusy(true);
    try {
      const res = await startStudyLoopToday(false);
      const quizId = String(res.quiz?.session_id || "").trim();
      if (quizId) {
        onStartPractice(quizId);
        return;
      }
      const tag = String(res.current_tag || "").trim();
      if (tag && !res.read_completed) {
        toast.message("Read Shorts for this step first — opening Notes");
        onOpenNotes(tag);
        onSelect(tag);
        return;
      }
      if (tag) onSelect(tag);
      toast.message("Path ready — use Continue after reading, or Start active focus");
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Could not start today’s path");
    } finally {
      setTodayBusy(false);
    }
  };

  return (
    <div className="space-y-5">
      {today && today.state !== "empty" && today.tags.length > 0 ? (
        <div className="rounded-xl border border-primary/30 bg-primary/5 p-3 flex flex-wrap items-center justify-between gap-2">
          <div className="min-w-0">
            <p className="text-sm font-medium">
              {today.state === "done"
                ? `Path done for ${today.day}`
                : today.steps?.length
                  ? `Today: ${today.steps.map((s) => s.label || s.tag).join(" → ")}`
                  : `Today: ${today.tags.join(" → ")}`}
            </p>
            <p className="text-[11px] text-muted-foreground mt-0.5">
              Assigned daily path · sits beside your Active Topics focus set
            </p>
          </div>
          {today.state !== "done" ? (
            <Button
              size="sm"
              className="gap-1 shrink-0"
              disabled={todayBusy || busy}
              onClick={() => void startDaily()}
            >
              {todayBusy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
              {today.state === "in_progress" ? "Continue path" : "Start today’s path"}
            </Button>
          ) : null}
        </div>
      ) : null}

      <div className="flex flex-wrap items-start justify-between gap-3">
        <p className="text-sm text-muted-foreground max-w-xl">
          Currently Active Topics until you finish focus practice. Cap {ACTIVE_TAG_CAP}.
        </p>
        <div className="flex flex-wrap gap-2">
          <Button
            size="sm"
            disabled={busy || active.length === 0}
            className="gap-1"
            onClick={onStartActiveFocus}
          >
            {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
            Start active focus
          </Button>
          <Button
            size="sm"
            variant="secondary"
            disabled={busy || !selectedId}
            onClick={onFocusSelected}
          >
            Focus selected
          </Button>
          <Button size="sm" variant="ghost" disabled={busy || fsrsReady === 0} onClick={onReviewDue}>
            Review due
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <StatCard value={`${active.length}/${ACTIVE_TAG_CAP}`} label="Active slots" />
        <StatCard
          value={String(activeWithDue)}
          label="Active with due"
          tone={activeWithDue > 0 ? "warn" : undefined}
        />
        <StatCard
          value={String(fsrsReady)}
          label="FSRS ready (active)"
          tone={fsrsReady > 0 ? "warn" : undefined}
        />
        <StatCard value={String(backlog.length)} label="Backlog" />
      </div>

      <ActiveBoard
        active={active}
        backlog={backlog}
        selectedId={selectedId}
        onSelect={onSelect}
        onActivate={onActivate}
        onPark={onPark}
        activeKind={activeKind}
        backlogKind={backlogKind}
        onActiveKind={onActiveKind}
        onBacklogKind={onBacklogKind}
        capHint={capHint}
      />

      {selectedId ? (
        <div className="rounded-xl border border-border/50 bg-background/40 px-3 py-2 flex flex-wrap items-center justify-between gap-2 text-xs">
          <span>
            Selected <span className="font-mono text-foreground">{selectedId}</span> — read as Shorts
          </span>
          <Button
            size="sm"
            variant="secondary"
            className="h-7 text-xs"
            onClick={() => onOpenNotes(selectedId)}
          >
            Open Shorts reader
          </Button>
        </div>
      ) : null}

      {showFsrs ? (
        <div className="gloss-panel rounded-xl p-4 space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-sm font-semibold">Ready to review (FSRS)</h3>
            <span
              className={`text-[11px] rounded-full border px-2 py-0.5 ${
                fsrsReady > 0
                  ? "border-amber-500/40 bg-amber-500/15 text-amber-900 dark:text-amber-100"
                  : "border-border/60 text-muted-foreground"
              }`}
            >
              {fsrsReady} cards
            </span>
          </div>
          <p className="text-xs text-muted-foreground">
            Due questions &amp; cards for topics in this active set — not gated by read.
            {activeIds.length === 0
              ? " Activate topics to filter; showing all due for today."
              : null}
          </p>
          {fsrsReady === 0 ? (
            <p className="text-xs text-muted-foreground">No due cards on active topics right now.</p>
          ) : (
            <ul className="divide-y rounded-lg border border-border/50 overflow-hidden">
              {activeDue.slice(0, 12).map((item) => (
                <li
                  key={`${item.domain}-${item.card_id ?? item.item_id}`}
                  className="flex items-center justify-between gap-2 px-3 py-2.5 text-sm bg-background/50"
                >
                  <div className="min-w-0">
                    <span className="text-[10px] uppercase text-muted-foreground mr-2">
                      {item.domain}
                    </span>
                    <span className="truncate">{item.label}</span>
                    {item.topic ? (
                      <span className="ml-2 font-mono text-[10px] text-muted-foreground">
                        {item.topic}
                      </span>
                    ) : null}
                  </div>
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-7 text-xs shrink-0"
                    onClick={() => onReviewItem(item)}
                  >
                    Review
                  </Button>
                </li>
              ))}
            </ul>
          )}
          {fsrsReady > 0 ? (
            <Button size="sm" variant="secondary" onClick={onReviewDue}>
              Review all ready ({fsrsReady})
            </Button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function StatCard({
  value,
  label,
  tone,
}: {
  value: string;
  label: string;
  tone?: "warn";
}) {
  return (
    <div
      className={`rounded-xl border p-3 ${
        tone === "warn"
          ? "border-amber-500/40 bg-amber-500/10"
          : "border-border/50 bg-background/40"
      }`}
    >
      <p className="text-lg font-semibold tabular-nums">{value}</p>
      <p className="text-[11px] text-muted-foreground mt-0.5">{label}</p>
    </div>
  );
}
