import { useEffect, useMemo, useState } from "react";
import { Loader2, Search, Tags } from "lucide-react";
import { Button } from "../../../app/components/ui/button";
import {
  fetchStudyLoopTags,
  type StudyLoopTag,
} from "../../../api/globalQuizClient";
import { resolvePillarWeight, tagSortScore } from "./pillarWeights";

type Props = {
  onSelect: (tagId: string) => void;
  disabled?: boolean;
};

export function TagPicker({ onSelect, disabled }: Props) {
  const [q, setQ] = useState("");
  const [tags, setTags] = useState<StudyLoopTag[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const t = window.setTimeout(() => {
      setLoading(true);
      setError(null);
      fetchStudyLoopTags({ q: q.trim() || undefined })
        .then((res) => {
          if (!cancelled) setTags(res.tags || []);
        })
        .catch((err: unknown) => {
          if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load tags");
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
    }, 200);
    return () => {
      cancelled = true;
      window.clearTimeout(t);
    };
  }, [q]);

  const sorted = useMemo(() => {
    const rows = (tags || []).map((t) => ({
      ...t,
      pillar_weight: t.pillar_weight ?? resolvePillarWeight(t),
    }));
    rows.sort((a, b) => {
      const scoreDiff = tagSortScore(b) - tagSortScore(a);
      if (scoreDiff !== 0) return scoreDiff;
      const la = String(a.label || a.id || "");
      const lb = String(b.label || b.id || "");
      return la.localeCompare(lb);
    });
    return rows;
  }, [tags]);

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-sm font-medium">
        <Tags className="h-4 w-4 text-primary" />
        Pick a tag
      </div>
      <div className="relative">
        <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
        <input
          type="search"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search tags (e.g. MT1-T02)"
          className="w-full rounded-md border bg-background pl-8 pr-3 py-2 text-sm"
          disabled={disabled}
        />
      </div>
      {error && <p className="text-xs text-destructive">{error}</p>}
      {loading ? (
        <div className="flex items-center gap-2 text-sm text-muted-foreground py-4">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading tags…
        </div>
      ) : sorted.length === 0 ? (
        <p className="text-xs text-muted-foreground py-2">No tags match.</p>
      ) : (
        <ul className="max-h-72 overflow-y-auto space-y-1.5 pr-1">
          {sorted.map((tag) => {
            const id = String(tag.id || "");
            const label = String(tag.label || id);
            const qCount = Number(tag.question_count || 0);
            const vCount = Number(tag.vocab_count || 0);
            const due = Number(tag.due_count || 0);
            return (
              <li key={id}>
                <button
                  type="button"
                  disabled={disabled || !id}
                  onClick={() => onSelect(id)}
                  className="w-full text-left rounded-lg border border-border/50 bg-background/40 px-3 py-2 hover:border-primary/40 hover:bg-primary/5 transition disabled:opacity-50"
                >
                  <div className="flex flex-wrap items-baseline justify-between gap-2">
                    <span className="text-sm font-medium">{label}</span>
                    <span className="text-[10px] text-muted-foreground uppercase tracking-wide">
                      {String(tag.kind || "tag")}
                    </span>
                  </div>
                  <p className="text-[11px] text-muted-foreground mt-0.5 font-mono">{id}</p>
                  <p className="text-[10px] text-muted-foreground mt-1">
                    {tag.has_read_card ? "read card" : "no read card"}
                    {qCount > 0 ? ` · ${qCount} Q` : ""}
                    {vCount > 0 ? ` · ${vCount} vocab` : ""}
                    {due > 0 ? ` · ${due} due` : ""}
                  </p>
                </button>
              </li>
            );
          })}
        </ul>
      )}
      {sorted[0] && (
        <Button
          size="sm"
          variant="outline"
          className="h-8 text-xs"
          disabled={disabled}
          onClick={() => onSelect(String(sorted[0].id))}
        >
          Start with top match
        </Button>
      )}
    </div>
  );
}
