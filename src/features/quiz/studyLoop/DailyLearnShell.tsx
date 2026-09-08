import { useCallback, useEffect, useState } from "react";
import { Brain, Loader2, RefreshCw } from "lucide-react";
import { toast, Toaster } from "sonner";
import { Button } from "../../../app/components/ui/button";
import {
  createStudyLoopSession,
  fetchStudyLoopTags,
  startStudyLoopPractice,
  type StudyLoopTag,
} from "../../../api/globalQuizClient";
import type { DueReviewItem } from "../types";
import {
  ACTIVE_TAG_CAP,
  loadActiveTagIds,
  loadStudyLoopPrefs,
  saveActiveTagIds,
  saveStudyLoopPrefs,
  type StudyLoopPrefs,
} from "./activeTagsStorage";
import type { KindFilter } from "./dailyLearnKinds";
import { LearnTab } from "./LearnTab";
import { NotesTab } from "./NotesTab";
import { QuestionsTab } from "./QuestionsTab";
import { SettingsTab, type LegacyTool } from "./SettingsTab";

export type DailyPageTab = "learn" | "notes" | "questions" | "settings";

const PAGE_TABS: { id: DailyPageTab; label: string }[] = [
  { id: "learn", label: "Learn" },
  { id: "notes", label: "Notes" },
  { id: "questions", label: "Questions" },
  { id: "settings", label: "Settings" },
];

type Props = {
  due: DueReviewItem[];
  dueCount: number;
  pageTab: DailyPageTab;
  onPageTab: (tab: DailyPageTab) => void;
  onStartPractice: (quizSessionId: string) => void;
  onStartDueReview: (opts?: { limit?: number; domains?: string[] }) => void;
  onOpenTool: (tool: LegacyTool) => void;
  onRefreshDue?: () => void;
};

export function DailyLearnShell({
  due,
  dueCount,
  pageTab,
  onPageTab,
  onStartPractice,
  onStartDueReview,
  onOpenTool,
  onRefreshDue,
}: Props) {
  const [tags, setTags] = useState<StudyLoopTag[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [activeIds, setActiveIds] = useState<string[]>(() => loadActiveTagIds());
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [activeKind, setActiveKind] = useState<KindFilter>("all");
  const [backlogKind, setBacklogKind] = useState<KindFilter>("all");
  const [capHint, setCapHint] = useState(false);
  const [prefs, setPrefs] = useState<StudyLoopPrefs>(() => loadStudyLoopPrefs());

  const refreshTags = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetchStudyLoopTags();
      const list = res.tags || [];
      setTags(list);
      setActiveIds((prev) => {
        const known = new Set(list.map((t) => String(t.id)));
        const next = prev.filter((id) => known.has(id));
        if (next.length !== prev.length) saveActiveTagIds(next);
        return next;
      });
      setSelectedId((cur) => {
        if (cur && list.some((t) => String(t.id) === cur)) return cur;
        const stored = loadActiveTagIds();
        return stored[0] || (list[0] ? String(list[0].id) : null);
      });
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Failed to load tags");
      setTags([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshTags();
  }, [refreshTags]);

  const setActiveAndPersist = (ids: string[]) => {
    const next = [...new Set(ids)].slice(0, ACTIVE_TAG_CAP);
    setActiveIds(next);
    saveActiveTagIds(next);
  };

  const activate = (id: string) => {
    if (activeIds.includes(id)) return;
    if (activeIds.length >= ACTIVE_TAG_CAP) {
      setCapHint(true);
      toast.message(`Active set full (cap ${ACTIVE_TAG_CAP})`);
      return;
    }
    setCapHint(false);
    setActiveAndPersist([...activeIds, id]);
    setSelectedId(id);
  };

  const park = (id: string) => {
    setCapHint(false);
    setActiveAndPersist(activeIds.filter((x) => x !== id));
  };

  const updatePrefs = (next: StudyLoopPrefs) => {
    setPrefs(next);
    saveStudyLoopPrefs(next);
  };

  /** Cards first → then questions for the same topic (never skip to another topic). */
  const focusTag = async (tagId: string) => {
    setBusy(true);
    try {
      const session = await createStudyLoopSession(tagId);
      if (!session.read_completed) {
        toast.message("Flash cards first — swipe through, then start questions");
        setSelectedId(tagId);
        onPageTab("notes");
        return;
      }
      const practice = await startStudyLoopPractice(session.session_id, 20);
      if (!practice.session_id) {
        throw new Error("Questions are not present for this topic.");
      }
      onStartPractice(practice.session_id);
    } catch (err: unknown) {
      const msg =
        err instanceof Error
          ? err.message
          : typeof err === "string"
            ? err
            : "Could not start practice";
      const lower = msg.toLowerCase();
      if (
        lower.includes("no_practice") ||
        lower.includes("not present") ||
        lower.includes("no math questions") ||
        msg === "HTTP 400"
      ) {
        toast.error("Questions are not present for this topic.");
      } else if (lower.includes("read_required") || lower.includes("flash cards")) {
        toast.message("Finish the flash cards first");
        setSelectedId(tagId);
        onPageTab("notes");
      } else {
        toast.error(msg);
      }
    } finally {
      setBusy(false);
    }
  };

  /** Prefer selected / first active topic — do not jump to a different Math Core tag. */
  const startActiveFocus = async () => {
    if (activeIds.length === 0) {
      toast.message("Activate topics first");
      return;
    }
    const prefer =
      (selectedId && activeIds.includes(selectedId) ? selectedId : null) || activeIds[0];
    await focusTag(prefer);
  };

  const focusSelected = async () => {
    if (!selectedId) {
      toast.message("Select a topic");
      return;
    }
    if (!activeIds.includes(selectedId)) {
      activate(selectedId);
    }
    await focusTag(selectedId);
  };

  return (
    <div className="space-y-5">
      <Toaster richColors position="top-center" />
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight flex items-center gap-2">
            <Brain className="h-6 w-6 text-primary" /> Daily Learn
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Active topics · notes · questions · FSRS — one Study Loop surface.
          </p>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => {
            void refreshTags();
            onRefreshDue?.();
          }}
          disabled={loading}
        >
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
        </Button>
      </header>

      <div className="flex flex-wrap gap-1.5">
        {PAGE_TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => onPageTab(t.id)}
            className={`rounded-full px-3 py-1 text-sm border transition ${
              pageTab === t.id
                ? "bg-primary/15 text-primary border-primary/40 font-medium"
                : "border-border/60 text-muted-foreground hover:text-foreground"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {loading && tags.length === 0 ? (
        <div className="flex items-center gap-2 text-sm text-muted-foreground py-10">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading Study Loop tags…
        </div>
      ) : null}

      {pageTab === "learn" ? (
        <LearnTab
          tags={tags}
          activeIds={activeIds}
          selectedId={selectedId}
          onSelect={setSelectedId}
          onActivate={activate}
          onPark={park}
          activeKind={activeKind}
          backlogKind={backlogKind}
          onActiveKind={setActiveKind}
          onBacklogKind={setBacklogKind}
          capHint={capHint}
          due={due}
          showFsrs={prefs.showFsrsUnderActive}
          busy={busy}
          onStartActiveFocus={() => void startActiveFocus()}
          onFocusSelected={() => void focusSelected()}
          onReviewDue={() => onStartDueReview({ limit: 25 })}
          onReviewItem={(item) =>
            onStartDueReview({ limit: 1, domains: [item.domain] })
          }
          onStartPractice={onStartPractice}
          onOpenNotes={(tagId) => {
            setSelectedId(tagId);
            onPageTab("notes");
          }}
        />
      ) : null}

      {pageTab === "notes" ? (
        <NotesTab
          tags={tags}
          selectedId={selectedId}
          onSelect={setSelectedId}
          onStartPractice={onStartPractice}
        />
      ) : null}

      {pageTab === "questions" ? <QuestionsTab focusTag={selectedId} /> : null}

      {pageTab === "settings" ? (
        <SettingsTab
          prefs={prefs}
          onPrefsChange={updatePrefs}
          dueCount={dueCount}
          onOpenTool={onOpenTool}
        />
      ) : null}
    </div>
  );
}
