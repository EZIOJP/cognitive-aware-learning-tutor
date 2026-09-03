import { useCallback, useEffect, useMemo, useState } from "react";
import { BookOpen, Layers, Loader2, Play, RefreshCw, Sparkles } from "lucide-react";
import { Button } from "../../../app/components/ui/button";
import {
  fetchStudyLoopTags,
  fetchTagImportance,
  fetchLowMasteryTags,
  putTagImportance,
  suggestTagImportance,
  importContentBank,
  syncContentBankToDb,
  type StudyLoopTag,
  type LowMasteryTag,
  type TagImportanceRow,
} from "../../../api/globalQuizClient";
import type { QuizDeckSummary } from "../types";

type GroupKey = "math" | "lecture" | "vocab" | "other" | "custom";

const GROUP_META: Record<GroupKey, { title: string; blurb: string }> = {
  math: { title: "Math (MT*)", blurb: "Curriculum tags · file / tag order" },
  lecture: { title: "Lecture notes (L*)", blurb: "Note sections · file order" },
  vocab: { title: "GRE vocab groups", blurb: "Indexed by group number" },
  other: { title: "Other tags", blurb: "Free tags (noisy ones may appear here)" },
  custom: { title: "Custom MCQ decks", blurb: "Decks you created on this page" },
};

type Props = {
  decks: QuizDeckSummary[];
  timeOpts: { time_limit_sec?: number; per_question_sec?: number };
  onPlay: (opts: {
    domain: "math" | "study" | "vocab" | "deck" | "review";
    config: Record<string, unknown>;
  }) => void;
  onDeleteDeck: (id: number) => void;
  onRefresh: () => void;
};

function groupOf(tag: StudyLoopTag): GroupKey {
  const g = String(tag.group || "");
  if (g === "math" || g === "lecture" || g === "vocab" || g === "other") return g;
  const id = String(tag.id || "").toUpperCase();
  if (id.startsWith("MT")) return "math";
  if (id.startsWith("L") && id.includes("-T")) return "lecture";
  if (String(tag.id || "").startsWith("vocab.group.")) return "vocab";
  return "other";
}

export function FlashDecksPanel({
  decks,
  timeOpts,
  onPlay,
  onDeleteDeck,
  onRefresh,
}: Props) {
  const [tags, setTags] = useState<StudyLoopTag[]>([]);
  const [loading, setLoading] = useState(true);
  const [populating, setPopulating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hint, setHint] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [showOther, setShowOther] = useState(false);
  const [impMap, setImpMap] = useState<Record<string, TagImportanceRow>>({});
  const [lowMastery, setLowMastery] = useState<LowMasteryTag[]>([]);
  const [suggesting, setSuggesting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [res, imp, low] = await Promise.all([
        fetchStudyLoopTags({ q: q.trim() || undefined }),
        fetchTagImportance().catch(() => ({ tags: {} as Record<string, TagImportanceRow> })),
        fetchLowMasteryTags().catch(() => ({ tags: [] as LowMasteryTag[] })),
      ]);
      setTags(res.tags || []);
      setImpMap(imp.tags || {});
      setLowMastery(low.tags || []);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load tags");
    } finally {
      setLoading(false);
    }
  }, [q]);

  useEffect(() => {
    const t = window.setTimeout(() => void load(), 150);
    return () => window.clearTimeout(t);
  }, [load]);

  const byGroup = useMemo(() => {
    const buckets: Record<GroupKey, StudyLoopTag[]> = {
      math: [],
      lecture: [],
      vocab: [],
      other: [],
      custom: [],
    };
    for (const tag of tags) {
      buckets[groupOf(tag)].push(tag);
    }
    return buckets;
  }, [tags]);

  const setImportance = async (tagId: string, value: number) => {
    try {
      const prev = impMap[tagId];
      const row = await putTagImportance(tagId, {
        importance: value,
        expected_updated_at: prev?.updated_at ?? null,
      });
      setImpMap((m) => ({ ...m, [tagId]: row }));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Could not save importance");
    }
  };

  const runSuggest = async () => {
    setSuggesting(true);
    setHint(null);
    try {
      const res = await suggestTagImportance();
      setHint(
        `Suggest: ${res.updated.length} updated, ${res.skipped_user.length} user-locked, ${res.dropped_invalid.length} invalid`
      );
      await load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Suggest failed");
    } finally {
      setSuggesting(false);
    }
  };

  const playLowMastery = (tag?: string) => {
    onPlay({
      domain: "review",
      config: { low_mastery: true, tag, count: 15, ...timeOpts },
    });
  };

  const playTag = (tag: StudyLoopTag) => {
    const id = String(tag.id || "");
    const g = groupOf(tag);
    if (g === "vocab") {
      const m = /vocab\.group\.(\d+)/i.exec(id);
      const gn = m ? Number(m[1]) : 1;
      onPlay({ domain: "vocab", config: { group_number: gn, ...timeOpts } });
      return;
    }
    if (g === "math") {
      onPlay({
        domain: "math",
        config: { note_topic_id: id, count: 15, ...timeOpts },
      });
      return;
    }
    // Lecture / other → study domain with note_topic_id when L*/MT*, else tag filter
    onPlay({
      domain: "study",
      config: {
        note_topic_id: id,
        count: 10,
        ...timeOpts,
      },
    });
  };

  const populate = async () => {
    setPopulating(true);
    setHint(null);
    try {
      await syncContentBankToDb("math");
      const seeded = await importContentBank({ kind: "math" });
      await load();
      onRefresh();
      setHint(
        `Populated math bank → FSRS (${seeded.cards_seeded ?? 0} cards, ${seeded.topics ?? 0} topics). Vocab groups + note tags are indexed live.`,
      );
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Populate failed");
    } finally {
      setPopulating(false);
    }
  };

  const renderTagList = (rows: StudyLoopTag[]) => (
    <ul className="divide-y rounded-lg border">
      {rows.map((tag) => {
        const id = String(tag.id || "");
        const qCount = Number(tag.question_count || 0);
        const vCount = Number(tag.vocab_count || 0);
        const files = (tag.note_paths || []) as string[];
        return (
          <li
            key={id}
            className="flex items-center justify-between gap-2 px-3 py-2 text-sm"
          >
            <div className="min-w-0">
              <p className="font-medium truncate">
                <span className="text-primary font-mono text-xs mr-2">{id}</span>
                {tag.label && tag.label !== id ? tag.label : null}
              </p>
              <p className="text-xs text-muted-foreground truncate">
                {qCount ? `${qCount} questions` : null}
                {qCount && vCount ? " · " : null}
                {vCount ? `${vCount} words` : null}
                {!qCount && !vCount ? "no items yet" : null}
                {files[0] ? ` · ${files[0]}` : null}
              </p>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <label className="text-[11px] text-muted-foreground flex items-center gap-1">
                Imp
                <select
                  className="rounded border bg-background text-xs px-1 py-0.5"
                  value={impMap[id]?.importance ?? 3}
                  onChange={(e) => void setImportance(id, Number(e.target.value))}
                >
                  {[1, 2, 3, 4, 5].map((n) => (
                    <option key={n} value={n}>
                      {n}
                    </option>
                  ))}
                </select>
                <span className="uppercase tracking-wide">
                  {impMap[id]?.source === "user"
                    ? "you"
                    : impMap[id]?.source === "claude"
                      ? "claude"
                      : "def"}
                </span>
              </label>
              <Button
                size="sm"
                disabled={!qCount && !vCount && groupOf(tag) !== "vocab"}
                onClick={() => playTag(tag)}
                className="gap-1"
              >
                <Play className="h-3.5 w-3.5" /> Play
              </Button>
            </div>
          </li>
        );
      })}
    </ul>
  );

  return (
    <section className="gloss-panel rounded-xl p-5 space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-medium flex items-center gap-2">
            <Layers className="h-4 w-4 text-primary" /> Flash decks by tag
          </h2>
          <p className="text-xs text-muted-foreground mt-1 max-w-xl">
            Indexed from notes (L*/MT*), math packs, and GRE vocab groups — same stitch as Study
            Loop. Ordered by file / tag number (not custom MCQ-only decks).
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant="outline" onClick={() => void load()} disabled={loading}>
            {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
            Refresh index
          </Button>
          <Button size="sm" variant="outline" onClick={() => void runSuggest()} disabled={suggesting}>
            {suggesting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
            Suggest importance
          </Button>
          <Button size="sm" onClick={() => void populate()} disabled={populating} className="gap-1">
            {populating ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Sparkles className="h-3.5 w-3.5" />
            )}
            Fast populate
          </Button>
        </div>
      </div>

      <input
        type="search"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Filter tags (e.g. MT1-T07, vocab.group.3)"
        className="w-full rounded border bg-background px-3 py-2 text-sm"
      />

      {error && <p className="text-sm text-destructive">{error}</p>}
      {hint && <p className="text-sm text-emerald-600 dark:text-emerald-400">{hint}</p>}

      {loading ? (
        <div className="flex items-center gap-2 text-sm text-muted-foreground py-6">
          <Loader2 className="h-4 w-4 animate-spin" /> Indexing tags…
        </div>
      ) : (
        (["math", "lecture", "vocab"] as const).map((key) => {
          const rows = byGroup[key];
          if (!rows.length) return null;
          return (
            <div key={key} className="space-y-2">
              <div className="flex items-center gap-2">
                <BookOpen className="h-3.5 w-3.5 text-muted-foreground" />
                <h3 className="text-sm font-semibold">{GROUP_META[key].title}</h3>
                <span className="text-[11px] text-muted-foreground">
                  {rows.length} · {GROUP_META[key].blurb}
                </span>
              </div>
              {renderTagList(rows)}
            </div>
          );
        })
      )}

      {!loading && byGroup.other.length > 0 && (
        <div className="space-y-2">
          <button
            type="button"
            className="text-xs text-muted-foreground underline-offset-2 hover:underline"
            onClick={() => setShowOther((v) => !v)}
          >
            {showOther ? "Hide" : "Show"} other tags ({byGroup.other.length})
          </button>
          {showOther && renderTagList(byGroup.other)}
        </div>
      )}

      <div className="space-y-2 border-t pt-4">
        <div className="flex items-center justify-between gap-2">
          <h3 className="text-sm font-semibold">Low Mastery</h3>
          <Button size="sm" disabled={!lowMastery.length} onClick={() => playLowMastery()}>
            Drill weak
          </Button>
        </div>
        <p className="text-xs text-muted-foreground">
          Tags not yet at their importance bar, including unpaid recycle debt.
        </p>
        {lowMastery.length === 0 ? (
          <p className="text-sm text-muted-foreground">No weak tags yet — play a deck first.</p>
        ) : (
          <ul className="divide-y rounded-lg border">
            {lowMastery.map((row) => (
              <li key={row.tag_id} className="flex items-center justify-between px-3 py-2 text-sm gap-2">
                <div>
                  <p className="font-mono text-xs">{row.tag_id}</p>
                  <p className="text-xs text-muted-foreground">
                    {row.cleared}/{row.total} cleared · {row.weak_count} weak · {row.owes_count} owing
                    · bar {row.bar}
                  </p>
                </div>
                <Button size="sm" onClick={() => playLowMastery(row.tag_id)}>
                  Drill
                </Button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="space-y-2 border-t pt-4">
        <h3 className="text-sm font-semibold">{GROUP_META.custom.title}</h3>
        <p className="text-xs text-muted-foreground">{GROUP_META.custom.blurb}</p>
        {decks.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No custom decks yet — use Create deck for one-off MCQs. Tag decks above are the main
            library.
          </p>
        ) : (
          <ul className="divide-y rounded-lg border">
            {decks.map((d) => (
              <li
                key={d.id}
                className="flex items-center justify-between px-3 py-2 text-sm gap-2"
              >
                <div>
                  <p className="font-medium">{d.title}</p>
                  <p className="text-xs text-muted-foreground">
                    {d.item_count} questions · {d.domain}
                  </p>
                </div>
                <div className="flex gap-1">
                  <Button
                    size="sm"
                    onClick={() =>
                      onPlay({ domain: "deck", config: { deck_id: d.id, ...timeOpts } })
                    }
                  >
                    Play
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => onDeleteDeck(d.id)}>
                    Delete
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
