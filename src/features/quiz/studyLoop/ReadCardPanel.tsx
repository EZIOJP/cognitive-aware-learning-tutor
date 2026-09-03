import { useEffect, useState } from "react";
import { AlertTriangle, Loader2, Save } from "lucide-react";
import { toast, Toaster } from "sonner";
import { Button } from "../../../app/components/ui/button";
import {
  QuizApiError,
  fetchStudyLoopReadCards,
  patchStudyLoopReadCard,
  type StudyLoopReadCard,
} from "../../../api/globalQuizClient";

type Props = {
  tag: string;
  cards: StudyLoopReadCard[];
  onCardsChange: (cards: StudyLoopReadCard[]) => void;
};

export function ReadCardPanel({ tag, cards, onCardsChange }: Props) {
  const [activeId, setActiveId] = useState<string | null>(cards[0]?.card_id ?? null);
  const [draft, setDraft] = useState("");
  const [title, setTitle] = useState("");
  const [mtime, setMtime] = useState<number | undefined>(undefined);
  const [saving, setSaving] = useState(false);
  const [conflict, setConflict] = useState(false);
  const [status, setStatus] = useState<string | null>(null);

  const active = cards.find((c) => c.card_id === activeId) || cards[0];

  useEffect(() => {
    if (!cards.length) {
      setActiveId(null);
      setDraft("");
      setTitle("");
      setMtime(undefined);
      setConflict(false);
      return;
    }
    const stillThere = activeId && cards.some((c) => c.card_id === activeId);
    const next = stillThere ? cards.find((c) => c.card_id === activeId)! : cards[0];
    if (!stillThere) setActiveId(next.card_id);
    setDraft(String(next.body_markdown || ""));
    setTitle(String(next.title || ""));
    setMtime(typeof next.mtime === "number" ? next.mtime : undefined);
    setConflict(false);
    setStatus(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only re-sync when card list identity/content changes
  }, [cards]);

  const selectCard = (cardId: string) => {
    const next = cards.find((c) => c.card_id === cardId);
    if (!next) return;
    setActiveId(cardId);
    setDraft(String(next.body_markdown || ""));
    setTitle(String(next.title || ""));
    setMtime(typeof next.mtime === "number" ? next.mtime : undefined);
    setConflict(false);
    setStatus(null);
  };

  const reloadLatest = async () => {
    try {
      const res = await fetchStudyLoopReadCards(tag);
      onCardsChange(res.items || []);
      setConflict(false);
      toast.message("Reloaded latest from disk");
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Reload failed");
    }
  };

  const save = async (overwrite: boolean) => {
    if (!active?.card_id) return;
    setSaving(true);
    setStatus(null);
    try {
      const body: { body_markdown: string; title?: string; expected_mtime?: number } = {
        body_markdown: draft,
      };
      if (title.trim()) body.title = title.trim();
      if (!overwrite && typeof mtime === "number") body.expected_mtime = mtime;
      const updated = await patchStudyLoopReadCard(active.card_id, body);
      const nextMtime = typeof updated.mtime === "number" ? updated.mtime : mtime;
      const merged = cards.map((c) =>
        c.card_id === active.card_id
          ? {
              ...c,
              ...updated,
              body_markdown: draft,
              title: title || c.title,
              mtime: nextMtime,
            }
          : c
      );
      onCardsChange(merged);
      setMtime(nextMtime);
      setConflict(false);
      setStatus("Saved");
      toast.success("Read card saved");
    } catch (err: unknown) {
      if (err instanceof QuizApiError && err.status === 409) {
        setConflict(true);
        toast.error(err.detail || "Note changed on disk. Reload before saving.");
        // Keep draft — never silent discard
      } else {
        const msg = err instanceof Error ? err.message : "Save failed";
        setStatus(msg);
        toast.error(msg);
      }
    } finally {
      setSaving(false);
    }
  };

  if (!cards.length) {
    return (
      <div className="rounded-lg border border-dashed border-border/60 p-4 text-sm text-muted-foreground">
        No read cards for <span className="font-mono text-foreground">{tag}</span>. You can still mark
        read and practice if questions exist.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <Toaster richColors position="top-center" />
      {cards.length > 1 && (
        <div className="flex flex-wrap gap-1.5">
          {cards.map((c) => (
            <button
              key={c.card_id}
              type="button"
              onClick={() => selectCard(c.card_id)}
              className={`text-[11px] px-2 py-1 rounded-md border transition ${
                (active?.card_id || "") === c.card_id
                  ? "border-primary bg-primary/10 text-primary"
                  : "border-border/50 text-muted-foreground hover:text-foreground"
              }`}
            >
              {String(c.title || c.tag || c.card_id)}
            </button>
          ))}
        </div>
      )}

      <div className="space-y-2">
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          className="w-full rounded-md border bg-background px-3 py-1.5 text-sm font-medium"
          placeholder="Title"
        />
        <p className="text-[10px] text-muted-foreground font-mono break-all">
          {active?.card_id}
          {typeof mtime === "number" ? ` · mtime ${mtime}` : ""}
        </p>
        <textarea
          value={draft}
          onChange={(e) => {
            setDraft(e.target.value);
            setStatus(null);
          }}
          rows={14}
          className="w-full rounded-md border bg-background px-3 py-2 text-sm font-mono leading-relaxed"
          spellCheck={false}
        />
      </div>

      {conflict && (
        <div
          className="rounded-lg border border-amber-500/60 bg-amber-500/10 px-3 py-2 space-y-2"
          role="alert"
        >
          <p className="text-xs flex items-start gap-1.5 text-amber-950 dark:text-amber-100">
            <AlertTriangle className="h-3.5 w-3.5 mt-0.5 shrink-0" />
            Note changed on disk. Your draft is still here — reload latest or overwrite anyway.
          </p>
          <div className="flex flex-wrap gap-2">
            <Button size="sm" variant="outline" className="h-7 text-xs" onClick={() => void reloadLatest()}>
              Reload latest
            </Button>
            <Button
              size="sm"
              className="h-7 text-xs"
              disabled={saving}
              onClick={() => void save(true)}
            >
              Overwrite anyway
            </Button>
          </div>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <Button size="sm" className="h-8 text-xs gap-1" disabled={saving} onClick={() => void save(false)}>
          {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
          Save
        </Button>
        {status && <span className="text-[11px] text-muted-foreground">{status}</span>}
      </div>
    </div>
  );
}
