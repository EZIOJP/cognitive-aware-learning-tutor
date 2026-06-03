import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router";
import {
  ArrowLeft,
  ChevronLeft,
  ChevronRight,
  Loader2,
  Shuffle,
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
import type { WordWithProgress } from "../../types";
import { hasVocabApi } from "../../../../api/vocabClient";
import {
  loadWordsForRead,
  markWordRead,
  type ReadListMode,
} from "../../store/vocabStore";
import { WordCard } from "./WordCard";

const MODE_TITLES: Record<ReadListMode, string> = {
  all: "All words",
  low: "Low mastery",
  struggling: "Struggling",
  learning: "Learning",
  practicing: "Practicing",
  mastered: "Mastered",
  due: "Due for review",
};

interface ReadModeProps {
  listMode?: ReadListMode;
  markOnNext?: boolean;
}

export function ReadMode({
  listMode = "all",
  markOnNext = true,
}: ReadModeProps) {
  const [words, setWords] = useState<WordWithProgress[]>([]);
  const [index, setIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [groupFilter, setGroupFilter] = useState<string>("all");
  const [search, setSearch] = useState("");

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const group =
        groupFilter === "all" ? null : Number.parseInt(groupFilter, 10);
      const list = await loadWordsForRead(listMode, group);
      setWords(list);
      setIndex(0);
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
        w.meaning.toLowerCase().includes(q)
    );
  }, [words, search]);

  useEffect(() => {
    setIndex(0);
  }, [search, groupFilter]);

  const current = filtered[index];
  const total = filtered.length;
  const progressPct = total > 0 ? ((index + 1) / total) * 100 : 0;

  const groups = useMemo(() => {
    const set = new Set(words.map((w) => w.group_number));
    return Array.from(set).sort((a, b) => a - b);
  }, [words]);

  const goNext = useCallback(async () => {
    if (total === 0) return;
    if (markOnNext && current) {
      try {
        await markWordRead(current.id);
      } catch {
        /* non-blocking */
      }
    }
    setIndex((i) => (i + 1) % total);
  }, [total, markOnNext, current]);

  const goPrev = useCallback(() => {
    if (total === 0) return;
    setIndex((i) => (i - 1 + total) % total);
  }, [total]);

  const goRandom = useCallback(() => {
    if (total <= 1) return;
    setIndex(Math.floor(Math.random() * total));
  }, [total]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement
      ) {
        return;
      }
      if (e.key === "ArrowRight" || e.key === " ") {
        e.preventDefault();
        goNext();
      } else if (e.key === "ArrowLeft") {
        e.preventDefault();
        goPrev();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [goNext, goPrev]);

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
      <div className="h-full flex flex-col gap-4 p-4">
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
          {listMode === "due" && (
            <p className="text-xs text-muted-foreground max-w-sm">
              Study words in All Words first — due dates appear after mastery
              reaches 3+.
            </p>
          )}
          <Link to="/gre-vocab/read">
            <Button variant="outline">Try all words</Button>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col gap-3 min-h-0">
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
      />
      <p className="text-[10px] text-muted-foreground px-1 -mt-1">
        {hasVocabApi()
          ? "Progress saves to your account when you advance."
          : "Offline mode — sign in to sync progress."}
      </p>

      <div className="flex-1 min-h-0">
        {current && <WordCard word={current} />}
      </div>

      <footer className="shrink-0 gloss-panel rounded-2xl px-4 py-3 flex flex-wrap items-center justify-between gap-3">
        <p className="text-xs text-muted-foreground hidden sm:block">
          Arrow keys or Space: next · Left: previous
        </p>
        <div className="flex items-center gap-2 w-full sm:w-auto justify-center">
          <Button variant="outline" size="sm" onClick={goPrev} aria-label="Previous">
            <ChevronLeft className="w-4 h-4 mr-1" />
            Prev
          </Button>
          <Button variant="outline" size="sm" onClick={goRandom} aria-label="Random">
            <Shuffle className="w-4 h-4" />
          </Button>
          <Button size="sm" onClick={goNext} aria-label="Next">
            Next
            <ChevronRight className="w-4 h-4 ml-1" />
          </Button>
        </div>
      </footer>
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
}) {
  return (
    <div className="shrink-0 gloss-panel rounded-2xl p-3 space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <Link
          to="/gre-vocab"
          className="gloss-dock-btn inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          Back
        </Link>
        <h1 className="text-sm font-semibold flex-1 min-w-[8rem]">{title}</h1>
        {total != null && total > 0 && (
          <span className="text-xs font-mono tabular-nums text-muted-foreground w-[4.5rem] text-right shrink-0">
            {index! + 1}/{total}
          </span>
        )}
      </div>

      {progressPct != null && (
        <Progress value={progressPct} className="h-1.5" />
      )}

      <div className="flex flex-wrap gap-2">
        <Input
          placeholder="Search word or meaning…"
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          className="h-9 flex-1 min-w-[140px] max-w-xs"
        />
        <Select value={groupFilter} onValueChange={onGroupChange}>
          <SelectTrigger className="h-9 w-[130px]">
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
    </div>
  );
}
