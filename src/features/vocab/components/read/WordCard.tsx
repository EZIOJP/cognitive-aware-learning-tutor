import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Loader2, Pencil, Sparkles, X } from "lucide-react";
import type { WordWithProgress, VocabWord } from "../../types";
import { useAuth } from "../../../../context/AuthContext";
import { authFetch } from "../../api/authClient";
import { Badge } from "../../../../app/components/ui/badge";
import { Button } from "../../../../app/components/ui/button";
import { Card } from "../../../../app/components/ui/card";
import { Input } from "../../../../app/components/ui/input";
import { Textarea } from "../../../../app/components/ui/textarea";

const EMPTY = "—";

function FieldBlock({
  label,
  value,
  children,
  className = "",
}: {
  label: string;
  value?: string;
  children?: ReactNode;
  className?: string;
}) {
  const empty = value !== undefined ? !value.trim() : false;
  return (
    <section className={className}>
      <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-1.5">
        {label}
      </h3>
      {children ?? (
        <p
          className={`text-sm leading-relaxed ${
            empty ? "text-muted-foreground/60 italic" : "text-foreground"
          }`}
        >
          {empty ? EMPTY : value}
        </p>
      )}
    </section>
  );
}

/** Horizontal auto-carousel for examples — gentle secondary motion. */
function ExamplesCarousel({
  examples,
}: {
  examples: { text: string }[];
}) {
  const slides = useMemo(() => {
    const filled = examples.map((e) => e.text.trim()).filter(Boolean);
    if (filled.length > 0) return filled;
    return [
      "Example 1 — Fill empty to generate",
      "Example 2 — Fill empty to generate",
      "Example 3 — Fill empty to generate",
    ];
  }, [examples]);

  const isPlaceholder = examples.every((e) => !(e.text || "").trim());
  const [paused, setPaused] = useState(false);
  const [active, setActive] = useState(0);

  useEffect(() => {
    setActive(0);
  }, [slides.join("|")]);

  useEffect(() => {
    if (paused || slides.length < 2) return;
    const id = window.setInterval(() => {
      setActive((i) => (i + 1) % slides.length);
    }, 3800);
    return () => window.clearInterval(id);
  }, [paused, slides.length]);

  // Duplicate track for continuous secondary marquee strip under the main slide
  const marquee = [...slides, ...slides];

  return (
    <section className="space-y-2" data-no-swipe>
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Examples
        </h3>
        <div className="flex gap-1">
          {slides.map((_, i) => (
            <button
              key={i}
              type="button"
              aria-label={`Example ${i + 1}`}
              className={`h-1.5 rounded-full transition-all ${
                i === active ? "w-4 bg-primary/70" : "w-1.5 bg-muted-foreground/30"
              }`}
              onClick={() => setActive(i)}
            />
          ))}
        </div>
      </div>

      <div
        className="relative overflow-hidden rounded-xl border border-border/50 bg-muted/20"
        onMouseEnter={() => setPaused(true)}
        onMouseLeave={() => setPaused(false)}
      >
        <div
          className="flex transition-transform duration-500 ease-out"
          style={{ transform: `translateX(-${active * 100}%)` }}
        >
          {slides.map((text, i) => (
            <div
              key={i}
              className="min-w-full shrink-0 px-4 py-4 text-sm leading-relaxed"
            >
              <span
                className={
                  isPlaceholder
                    ? "text-muted-foreground/70 italic"
                    : "text-foreground"
                }
              >
                {text}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Secondary continuous horizontal drift */}
      <div
        className="relative overflow-hidden rounded-lg border border-dashed border-border/40 py-2 opacity-80"
        onMouseEnter={() => setPaused(true)}
        onMouseLeave={() => setPaused(false)}
        aria-hidden
      >
        <div
          className="vocab-examples-marquee flex w-max gap-3 px-2"
          style={{ animationPlayState: paused ? "paused" : "running" }}
        >
          {marquee.map((text, i) => (
            <span
              key={`${i}-${text.slice(0, 12)}`}
              className={`shrink-0 max-w-[220px] truncate rounded-md border border-border/40 bg-background/60 px-2.5 py-1 text-[11px] ${
                isPlaceholder ? "text-muted-foreground/60 italic" : "text-muted-foreground"
              }`}
            >
              {text}
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}

interface WordCardProps {
  word: WordWithProgress;
  /** Called after AI rewrite or manual save so Read Mode can refresh. */
  onWordUpdated?: (word: VocabWord) => void;
  /** Hide Edit / Fill empty in the card header (parent toolbar owns them). */
  hideActions?: boolean;
  /** Controlled edit mode — when set, parent drives open/close. */
  editing?: boolean;
  onEditingChange?: (editing: boolean) => void;
  /** External AI busy flag (toolbar Fill empty). */
  aiBusy?: boolean;
}

type EditDraft = {
  pronunciation: string;
  connotation: string;
  meaning: string;
  story_mnemonic: string;
  etymology: string;
  examplesText: string;
  synonymsText: string;
  antonymsText: string;
};

function masteryVariant(mastery: number) {
  if (mastery < 0) return "destructive" as const;
  if (mastery <= 2) return "secondary" as const;
  if (mastery <= 5) return "default" as const;
  return "outline" as const;
}

function draftFromWord(word: WordWithProgress): EditDraft {
  return {
    pronunciation: word.pronunciation || "",
    connotation: word.connotation || "",
    meaning: word.meaning || "",
    story_mnemonic: word.story_mnemonic || "",
    etymology: word.etymology || "",
    examplesText: (word.examples || []).map((e) => e.text).join("\n"),
    synonymsText: (word.synonyms || []).join(", "),
    antonymsText: (word.antonyms || []).join(", "),
  };
}

function splitList(raw: string): string[] {
  return raw
    .split(/[,;\n]/)
    .map((s) => s.trim())
    .filter(Boolean)
    .slice(0, 12);
}

export function WordCard({
  word,
  onWordUpdated,
  hideActions = false,
  editing: editingProp,
  onEditingChange,
  aiBusy = false,
}: WordCardProps) {
  const { token, isAdmin } = useAuth();
  const [busy, setBusy] = useState(false);
  const [editingLocal, setEditingLocal] = useState(false);
  const editing = editingProp ?? editingLocal;
  const setEditing = (next: boolean) => {
    onEditingChange?.(next);
    if (editingProp === undefined) setEditingLocal(next);
  };
  const [draft, setDraft] = useState<EditDraft>(() => draftFromWord(word));
  const [error, setError] = useState<string | null>(null);
  const breakdown = word.word_breakdown;
  const actionBusy = busy || aiBusy;

  useEffect(() => {
    if (!editing) setDraft(draftFromWord(word));
  }, [word, editing]);

  const runAi = async (overwrite: boolean) => {
    if (!token || !isAdmin || actionBusy) return;
    setBusy(true);
    setError(null);
    try {
      const { data } = await authFetch(
        `/words/${word.id}/enrich?overwrite=${overwrite ? "true" : "false"}`,
        token,
        { method: "POST" },
      );
      const updated = (data as { word?: VocabWord }).word;
      if (updated && onWordUpdated) onWordUpdated(updated);
      setEditing(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "AI enrich failed");
    } finally {
      setBusy(false);
    }
  };

  const saveEdit = async () => {
    if (!token || !isAdmin || actionBusy) return;
    setBusy(true);
    setError(null);
    try {
      const examples = draft.examplesText
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean)
        .map((text) => ({ text }));
      const { data } = await authFetch(`/words/${word.id}`, token, {
        method: "PUT",
        body: JSON.stringify({
          pronunciation: draft.pronunciation.trim(),
          connotation: draft.connotation.trim(),
          meaning: draft.meaning.trim(),
          story_mnemonic: draft.story_mnemonic.trim(),
          etymology: draft.etymology.trim(),
          examples,
          synonyms: splitList(draft.synonymsText),
          antonyms: splitList(draft.antonymsText),
        }),
      });
      const updated = data as VocabWord;
      if (updated && onWordUpdated) onWordUpdated(updated);
      setEditing(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card className="gloss-panel h-full flex flex-col overflow-hidden border-0 shadow-lg select-none">
      <header className="shrink-0 px-4 sm:px-5 py-3 sm:py-4 border-b border-border/60 bg-gradient-to-r from-blue-50/80 to-violet-50/50 dark:from-zinc-900/80 dark:to-zinc-800/50">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <h2 className="text-2xl sm:text-3xl font-bold tracking-tight break-words">
                {word.word}
              </h2>
              {!editing && (
                <span
                  className={`text-sm italic ${
                    (word.connotation || "").trim()
                      ? "text-violet-700/90 dark:text-violet-300"
                      : "text-muted-foreground/50"
                  }`}
                >
                  {(word.connotation || "").trim() || "connotation —"}
                </span>
              )}
            </div>
            {!editing && (
              <p
                className={`italic mt-1 text-sm ${
                  (word.pronunciation || "").trim()
                    ? "text-muted-foreground"
                    : "text-muted-foreground/50"
                }`}
              >
                /{(word.pronunciation || "").trim() || "pronunciation —"}/
              </p>
            )}
          </div>
          <div className="flex flex-wrap gap-2 shrink-0 items-center">
            <Badge variant={masteryVariant(word.mastery)} className="font-mono tabular-nums min-w-[3rem] justify-center">
              M{word.mastery}
            </Badge>
            <Badge variant="outline">G{word.group_number}</Badge>
            {word.priority != null && word.priority >= 3 && (
              <Badge variant="default" className="text-[10px]">
                {word.priority_label || `P${word.priority}`}
                {word.source_count != null ? ` ·${word.source_count}` : ""}
              </Badge>
            )}
            {!(word.meaning || "").trim() && (
              <Badge variant="secondary" className="text-[10px]">
                Needs card content
              </Badge>
            )}
            {word.is_due && (
              <Badge variant="destructive" className="text-[10px]">
                Due
              </Badge>
            )}
            {isAdmin && !hideActions && !editing && (
              <>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  className="h-7 gap-1 text-xs"
                  disabled={actionBusy}
                  onClick={() => {
                    setDraft(draftFromWord(word));
                    setEditing(true);
                    setError(null);
                  }}
                >
                  <Pencil className="w-3.5 h-3.5" />
                  Edit
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="secondary"
                  className="h-7 gap-1 text-xs"
                  disabled={actionBusy}
                  onClick={() => void runAi(false)}
                  title="Fill empty fields only (keeps existing text)"
                >
                  {actionBusy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
                  Gen AI
                </Button>
              </>
            )}
            {isAdmin && editing && (
              <>
                <Button
                  type="button"
                  size="sm"
                  className="h-7 text-xs"
                  disabled={actionBusy || !draft.meaning.trim()}
                  onClick={() => void saveEdit()}
                >
                  {busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : "Save"}
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  className="h-7 gap-1 text-xs"
                  disabled={actionBusy}
                  onClick={() => {
                    setEditing(false);
                    setError(null);
                    setDraft(draftFromWord(word));
                  }}
                >
                  <X className="w-3.5 h-3.5" />
                  Cancel
                </Button>
              </>
            )}
          </div>
        </div>
        {error && <p className="text-xs text-destructive mt-2">{error}</p>}
      </header>

      <div className="flex-1 overflow-y-auto p-5 space-y-5">
        {editing ? (
          <>
            <label className="block space-y-1">
              <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Connotation (English tone / feel)
              </span>
              <Input
                value={draft.connotation}
                onChange={(e) => setDraft((d) => ({ ...d, connotation: e.target.value }))}
                placeholder="e.g. warm praise, formal disapproval"
                disabled={actionBusy}
              />
            </label>
            <label className="block space-y-1">
              <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Pronunciation (how it sounds)
              </span>
              <Input
                value={draft.pronunciation}
                onChange={(e) => setDraft((d) => ({ ...d, pronunciation: e.target.value }))}
                placeholder="uh-LAS-ri-tee"
                disabled={actionBusy}
              />
            </label>
            <label className="block space-y-1">
              <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Meaning
              </span>
              <Textarea
                className="min-h-[72px]"
                value={draft.meaning}
                onChange={(e) => setDraft((d) => ({ ...d, meaning: e.target.value }))}
                disabled={actionBusy}
              />
            </label>
            <label className="block space-y-1">
              <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Story mnemonic
              </span>
              <Textarea
                className="min-h-[72px]"
                value={draft.story_mnemonic}
                onChange={(e) => setDraft((d) => ({ ...d, story_mnemonic: e.target.value }))}
                placeholder="Funny / sticky memory hook"
                disabled={actionBusy}
              />
            </label>
            <label className="block space-y-1">
              <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Etymology
              </span>
              <Textarea
                className="min-h-[56px]"
                value={draft.etymology}
                onChange={(e) => setDraft((d) => ({ ...d, etymology: e.target.value }))}
                disabled={actionBusy}
              />
            </label>
            <label className="block space-y-1">
              <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Examples (one per line)
              </span>
              <Textarea
                className="min-h-[100px] font-mono text-sm"
                value={draft.examplesText}
                onChange={(e) => setDraft((d) => ({ ...d, examplesText: e.target.value }))}
                disabled={actionBusy}
              />
            </label>
            <label className="block space-y-1">
              <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Synonyms (comma-separated)
              </span>
              <Input
                value={draft.synonymsText}
                onChange={(e) => setDraft((d) => ({ ...d, synonymsText: e.target.value }))}
                disabled={actionBusy}
              />
            </label>
            <label className="block space-y-1">
              <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Antonyms (comma-separated)
              </span>
              <Input
                value={draft.antonymsText}
                onChange={(e) => setDraft((d) => ({ ...d, antonymsText: e.target.value }))}
                disabled={actionBusy}
              />
            </label>
            <div className="flex flex-wrap gap-2 pt-1">
              <Button
                type="button"
                size="sm"
                variant="secondary"
                disabled={actionBusy}
                onClick={() => void runAi(false)}
              >
                {actionBusy ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" /> : <Sparkles className="w-3.5 h-3.5 mr-1" />}
                Gen AI (empty)
              </Button>
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={actionBusy}
                onClick={() => void runAi(true)}
              >
                Remake all (AI)
              </Button>
            </div>
          </>
        ) : (
          <>
            <FieldBlock label="Meaning" value={word.meaning || ""}>
              <p
                className={`text-base leading-relaxed ${
                  (word.meaning || "").trim()
                    ? "text-foreground"
                    : "text-muted-foreground/60 italic"
                }`}
              >
                {(word.meaning || "").trim() || EMPTY}
              </p>
            </FieldBlock>

            <FieldBlock
              label="Story mnemonic"
              className="rounded-xl bg-amber-50/80 dark:bg-amber-950/30 p-4 border border-amber-200/50 dark:border-amber-800/40"
            >
              <p
                className={`text-sm leading-relaxed ${
                  (word.story_mnemonic || "").trim()
                    ? "text-foreground"
                    : "text-muted-foreground/60 italic"
                }`}
              >
                {(word.story_mnemonic || "").trim() || EMPTY}
              </p>
            </FieldBlock>

            <FieldBlock label="Etymology" value={word.etymology || ""} />

            <FieldBlock label="Word parts">
              <div className="flex flex-wrap gap-2">
                <Badge variant="secondary">
                  Prefix: {(breakdown?.prefix || "").trim() || EMPTY}
                </Badge>
                <Badge variant="secondary">
                  Root: {(breakdown?.root || "").trim() || EMPTY}
                </Badge>
                <Badge variant="secondary">
                  Suffix: {(breakdown?.suffix || "").trim() || EMPTY}
                </Badge>
              </div>
            </FieldBlock>

            <FieldBlock label="Synonyms">
              <div className="flex flex-wrap gap-1.5">
                {(word.synonyms && word.synonyms.length > 0
                  ? word.synonyms
                  : [EMPTY]
                ).map((s, i) => (
                  <Badge
                    key={`${s}-${i}`}
                    variant="outline"
                    className={`font-normal ${s === EMPTY ? "text-muted-foreground/60 italic" : ""}`}
                  >
                    {s}
                  </Badge>
                ))}
              </div>
            </FieldBlock>

            <FieldBlock label="Antonyms">
              <div className="flex flex-wrap gap-1.5">
                {(word.antonyms && word.antonyms.length > 0
                  ? word.antonyms
                  : [EMPTY]
                ).map((a, i) => (
                  <Badge
                    key={`${a}-${i}`}
                    variant="outline"
                    className={`font-normal ${a === EMPTY ? "text-muted-foreground/60 italic" : ""}`}
                  >
                    {a}
                  </Badge>
                ))}
              </div>
            </FieldBlock>

            <ExamplesCarousel examples={word.examples || []} />
          </>
        )}
      </div>
    </Card>
  );
}
