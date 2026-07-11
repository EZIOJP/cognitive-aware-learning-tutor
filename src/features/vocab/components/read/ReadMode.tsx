import { useCallback, useEffect, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import { Link } from "react-router";
import {
  ArrowLeft,
  ChevronLeft,
  ChevronRight,
  Loader2,
  Pencil,
  Shuffle,
  Sparkles,
} from "lucide-react";
import { Button } from "../../../../app/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../../../../app/components/ui/select";
import { Input } from "../../../../app/components/ui/input";
import { Progress } from "../../../../app/components/ui/progress";
import type { WordWithProgress, VocabWord } from "../../types";
import { hasVocabApi } from "../../../../api/vocabClient";
import {
  loadWordsForRead,
  markWordRead,
  type ReadListMode,
} from "../../store/vocabStore";
import { WordCard } from "./WordCard";
import { useAuth } from "../../../../context/AuthContext";
import { authFetch } from "../../api/authClient";

const MODE_TITLES: Record<ReadListMode, string> = {
  all: "All words",
  low: "Low mastery",
  struggling: "Struggling",
  learning: "Learning",
  practicing: "Practicing",
  mastered: "Mastered",
  due: "Due for review",
};

const SWIPE_MIN_PX = 56;
const SWIPE_RATIO = 1.25;

interface ReadModeProps {
  listMode?: ReadListMode;
  markOnNext?: boolean;
}

export function ReadMode({
  listMode = "all",
  markOnNext = true,
}: ReadModeProps) {
  const { token, isAdmin } = useAuth();
  const [words, setWords] = useState<WordWithProgress[]>([]);
  const [index, setIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [groupFilter, setGroupFilter] = useState<string>("all");
  const [search, setSearch] = useState("");
  const [fillBusy, setFillBusy] = useState(false);
  const [fillMsg, setFillMsg] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [dragX, setDragX] = useState(0);
  const [dragging, setDragging] = useState(false);
  const pointerRef = useRef<{
    id: number;
    x: number;
    y: number;
    active: boolean;
  } | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const group =
        groupFilter === "all" ? null : Number.parseInt(groupFilter, 10);
      const list = await loadWordsForRead(listMode, group);
      setWords(list);
      setIndex(0);
      setEditing(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load words");
      setWords([]);
    } finally {
      setLoading(false);
    }
  }, [listMode, groupFilter]);

  useEffect(() => {
    reload();
  }, [reload]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return words;
    return words.filter(
      (w) =>
        w.word.toLowerCase().includes(q) ||
        (w.meaning || "").toLowerCase().includes(q),
    );
  }, [words, search]);

  useEffect(() => {
    setIndex(0);
    setEditing(false);
  }, [search, groupFilter]);

  const current = filtered[index];
  const total = filtered.length;
  const progressPct = total > 0 ? ((index + 1) / total) * 100 : 0;

  const patchWord = useCallback((updated: VocabWord) => {
    setWords((prev) =>
      prev.map((w) =>
        w.id === updated.id
          ? {
              ...w,
              ...updated,
              mastery: w.mastery,
              times_asked: w.times_asked,
              times_correct: w.times_correct,
              accuracy_rate: w.accuracy_rate,
              is_due: w.is_due,
            }
          : w,
      ),
    );
  }, []);

  const fillEmptyCurrent = useCallback(async () => {
    if (!token || !isAdmin || !current || fillBusy || editing) return;
    setFillBusy(true);
    setFillMsg(null);
    try {
      const { data } = await authFetch(
        `/words/${current.id}/enrich?overwrite=false`,
        token,
        { method: "POST" },
      );
      const updated = (data as { word?: VocabWord }).word;
      if (updated) {
        patchWord(updated);
        setFillMsg(`Filled empty fields on ${updated.word}`);
      }
    } catch (e) {
      setFillMsg(e instanceof Error ? e.message : "Gen AI failed");
    } finally {
      setFillBusy(false);
    }
  }, [token, isAdmin, current, fillBusy, editing, patchWord]);

  const groups = useMemo(() => {
    const set = new Set(words.map((w) => w.group_number));
    return Array.from(set).sort((a, b) => a - b);
  }, [words]);

  const goNext = useCallback(async () => {
    if (total === 0 || editing) return;
    if (markOnNext && current) {
      try {
        await markWordRead(current.id);
      } catch {
        /* non-blocking */
      }
    }
    setEditing(false);
    setIndex((i) => (i + 1) % total);
  }, [total, markOnNext, current, editing]);

  const goPrev = useCallback(() => {
    if (total === 0 || editing) return;
    setEditing(false);
    setIndex((i) => (i - 1 + total) % total);
  }, [total, editing]);

  const goRandom = useCallback(() => {
    if (total <= 1 || editing) return;
    setEditing(false);
    setIndex(Math.floor(Math.random() * total));
  }, [total, editing]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement ||
        e.target instanceof HTMLSelectElement
      ) {
        return;
      }
      if (editing) return;
      if (e.key === "ArrowRight" || e.key === " ") {
        e.preventDefault();
        void goNext();
      } else if (e.key === "ArrowLeft") {
        e.preventDefault();
        goPrev();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [goNext, goPrev, editing]);

  const endSwipe = useCallback(
    (dx: number, dy: number) => {
      setDragging(false);
      setDragX(0);
      if (editing) return;
      if (Math.abs(dx) < SWIPE_MIN_PX) return;
      if (Math.abs(dx) < Math.abs(dy) * SWIPE_RATIO) return;
      if (dx < 0) void goNext();
      else goPrev();
    },
    [editing, goNext, goPrev],
  );

  const onPointerDown = (e: ReactPointerEvent<HTMLDivElement>) => {
    if (editing) return;
    if ((e.target as HTMLElement).closest("button, a, input, textarea, select, [data-no-swipe]")) {
      return;
    }
    pointerRef.current = { id: e.pointerId, x: e.clientX, y: e.clientY, active: true };
    setDragging(true);
    setDragX(0);
    (e.currentTarget as HTMLElement).setPointerCapture?.(e.pointerId);
  };

  const onPointerMove = (e: ReactPointerEvent<HTMLDivElement>) => {
    const p = pointerRef.current;
    if (!p?.active || p.id !== e.pointerId) return;
    const dx = e.clientX - p.x;
    const dy = e.clientY - p.y;
    if (Math.abs(dx) > Math.abs(dy)) {
      setDragX(Math.max(-120, Math.min(120, dx * 0.45)));
    }
  };

  const onPointerUp = (e: ReactPointerEvent<HTMLDivElement>) => {
    const p = pointerRef.current;
    if (!p?.active || p.id !== e.pointerId) return;
    const dx = e.clientX - p.x;
    const dy = e.clientY - p.y;
    pointerRef.current = null;
    endSwipe(dx, dy);
  };

  const onPointerCancel = () => {
    pointerRef.current = null;
    setDragging(false);
    setDragX(0);
  };

  if (loading) {
    return (
      <div className="h-full flex flex-col items-center justify-center gap-3 text-muted-foreground">
        <Loader2 className="w-8 h-8 animate-spin" />
        <p className="text-sm">Loading vocabulary…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="h-full flex flex-col items-center justify-center gap-4 p-6 text-center">
        <p className="text-destructive font-medium">{error}</p>
        <Button onClick={reload}>Retry</Button>
        <Link to="/gre-vocab" className="text-sm text-primary hover:underline">
          Back to GRE Vocab
        </Link>
      </div>
    );
  }

  if (total === 0) {
    return (
      <div className="h-full flex flex-col gap-3 min-h-0">
        <ReadToolbar
          title={MODE_TITLES[listMode]}
          groups={groups}
          groupFilter={groupFilter}
          onGroupChange={setGroupFilter}
          search={search}
          onSearchChange={setSearch}
        />
        <div className="flex-1 gloss-panel rounded-2xl flex flex-col items-center justify-center gap-3 p-8 text-center">
          <p className="text-muted-foreground">
            No words match this list{listMode === "due" ? " yet" : ""}.
          </p>
          <Link to="/gre-vocab/read">
            <Button variant="outline">Try all words</Button>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full min-h-0 flex flex-col gap-2">
      <ReadToolbar
        title={MODE_TITLES[listMode]}
        groups={groups}
        groupFilter={groupFilter}
        onGroupChange={setGroupFilter}
        search={search}
        onSearchChange={setSearch}
        index={index}
        total={total}
        progressPct={progressPct}
        showAdminActions={Boolean(isAdmin && current)}
        fillBusy={fillBusy}
        editing={editing}
        onGenAi={() => void fillEmptyCurrent()}
        onEdit={() => setEditing(true)}
        fillMsg={fillMsg}
        onRandom={goRandom}
      />

      {/* Full-screen shorts-style card stage */}
      <div className="relative flex-1 min-h-0 overflow-hidden rounded-2xl">
        {/* Edge tap zones */}
        <button
          type="button"
          aria-label="Previous word"
          disabled={editing}
          className="absolute left-0 top-0 bottom-0 z-20 w-10 sm:w-14 touch-manipulation opacity-0 hover:opacity-100 focus-visible:opacity-100 transition-opacity disabled:pointer-events-none"
          onClick={goPrev}
        >
          <span className="flex h-full items-center justify-center bg-gradient-to-r from-background/50 to-transparent">
            <ChevronLeft className="w-7 h-7 text-foreground/70" />
          </span>
        </button>
        <button
          type="button"
          aria-label="Next word"
          disabled={editing}
          className="absolute right-0 top-0 bottom-0 z-20 w-10 sm:w-14 touch-manipulation opacity-0 hover:opacity-100 focus-visible:opacity-100 transition-opacity disabled:pointer-events-none"
          onClick={() => void goNext()}
        >
          <span className="flex h-full items-center justify-center bg-gradient-to-l from-background/50 to-transparent">
            <ChevronRight className="w-7 h-7 text-foreground/70" />
          </span>
        </button>

        <div
          className="h-full touch-pan-y"
          style={{
            transform: `translateX(${dragX}px)`,
            transition: dragging ? "none" : "transform 180ms ease-out",
          }}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerCancel={onPointerCancel}
        >
          {current && (
            <WordCard
              key={current.id}
              word={current}
              onWordUpdated={patchWord}
              hideActions
              editing={editing}
              onEditingChange={setEditing}
              aiBusy={fillBusy}
            />
          )}
        </div>

        <p className="pointer-events-none absolute bottom-2 left-1/2 z-10 -translate-x-1/2 rounded-full bg-background/70 px-2.5 py-0.5 text-[10px] text-muted-foreground backdrop-blur-sm">
          Swipe ← → · {hasVocabApi() ? "progress saves on next" : "offline"}
        </p>
      </div>
    </div>
  );
}

function ReadToolbar({
  title,
  groups,
  groupFilter,
  onGroupChange,
  search,
  onSearchChange,
  index,
  total,
  progressPct,
  showAdminActions,
  fillBusy,
  editing,
  onGenAi,
  onEdit,
  fillMsg,
  onRandom,
}: {
  title: string;
  groups: number[];
  groupFilter: string;
  onGroupChange: (v: string) => void;
  search: string;
  onSearchChange: (v: string) => void;
  index?: number;
  total?: number;
  progressPct?: number;
  showAdminActions?: boolean;
  fillBusy?: boolean;
  editing?: boolean;
  onGenAi?: () => void;
  onEdit?: () => void;
  fillMsg?: string | null;
  onRandom?: () => void;
}) {
  return (
    <div className="shrink-0 gloss-panel rounded-2xl px-3 py-2 space-y-2" data-no-swipe>
      <div className="flex flex-wrap items-center gap-2">
        <Link
          to="/gre-vocab"
          className="gloss-dock-btn inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          Back
        </Link>
        <h1 className="text-sm font-semibold flex-1 min-w-[6rem] truncate">{title}</h1>
        {total != null && total > 0 && (
          <span className="text-xs font-mono tabular-nums text-muted-foreground shrink-0">
            {index! + 1}/{total}
          </span>
        )}
        {onRandom && (
          <Button
            type="button"
            size="sm"
            variant="ghost"
            className="h-8 w-8 p-0"
            onClick={onRandom}
            disabled={editing}
            aria-label="Random word"
          >
            <Shuffle className="w-3.5 h-3.5" />
          </Button>
        )}
        {showAdminActions && (
          <>
            <Button
              type="button"
              size="sm"
              variant="outline"
              className="h-8 gap-1 text-xs"
              disabled={fillBusy || editing}
              onClick={onEdit}
            >
              <Pencil className="w-3.5 h-3.5" />
              Edit
            </Button>
            <Button
              type="button"
              size="sm"
              variant="secondary"
              className="h-8 gap-1 text-xs"
              disabled={fillBusy || editing}
              onClick={onGenAi}
              title="AI: fill only empty fields"
            >
              {fillBusy ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Sparkles className="w-3.5 h-3.5" />
              )}
              Gen AI
            </Button>
          </>
        )}
      </div>

      {progressPct != null && <Progress value={progressPct} className="h-1" />}

      <div className="flex flex-wrap gap-2 items-center">
        <Input
          placeholder="Search…"
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          className="h-8 flex-1 min-w-[120px] max-w-xs text-sm"
        />
        <Select value={groupFilter} onValueChange={onGroupChange}>
          <SelectTrigger className="h-8 w-[120px] text-xs">
            <SelectValue placeholder="Group" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All groups</SelectItem>
            {groups.map((g) => (
              <SelectItem key={g} value={String(g)}>
                Group {g}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      {fillMsg && <p className="text-[11px] text-muted-foreground">{fillMsg}</p>}
    </div>
  );
}
