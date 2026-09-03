import { useEffect, useState } from "react";
import { Loader2, PenLine } from "lucide-react";
import { toast } from "sonner";
import { Button } from "../../../app/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "../../../app/components/ui/sheet";
import {
  fetchStudyLoopQuestions,
  patchStudyLoopQuestion,
} from "../../../api/globalQuizClient";

type QuestionRow = Record<string, unknown> & {
  id?: string;
  prompt?: string;
  question?: string;
  expected_answer?: string;
  answer?: string;
  answer_format?: string;
  open?: boolean;
  solution_steps?: string;
};

type Props = {
  tag: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

export function QuestionEditor({ tag, open, onOpenChange }: Props) {
  const [items, setItems] = useState<QuestionRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [savingId, setSavingId] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<Record<string, string>>({});

  useEffect(() => {
    if (!open || !tag) return;
    let cancelled = false;
    setLoading(true);
    fetchStudyLoopQuestions({ tag })
      .then((res) => {
        if (cancelled) return;
        const rows = (res.items || []) as QuestionRow[];
        setItems(rows);
        const next: Record<string, string> = {};
        for (const q of rows) {
          const id = String(q.id || "");
          if (!id) continue;
          next[id] = String(q.expected_answer || q.answer || "");
        }
        setDrafts(next);
      })
      .catch((err: unknown) => {
        if (!cancelled) toast.error(err instanceof Error ? err.message : "Failed to load questions");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open, tag]);

  const openItems = items.filter((q) => q.open === true || !String(q.expected_answer || q.answer || "").trim());

  const saveAnswer = async (q: QuestionRow) => {
    const id = String(q.id || "");
    if (!id) return;
    setSavingId(id);
    try {
      const answer = drafts[id] ?? "";
      await patchStudyLoopQuestion(id, {
        expected_answer: answer,
        answer,
        answer_format: answer.trim() ? "text" : "open",
      });
      setItems((prev) =>
        prev.map((row) =>
          String(row.id) === id
            ? { ...row, expected_answer: answer, answer, open: !answer.trim() }
            : row
        )
      );
      toast.success("Answer saved");
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSavingId(null);
    }
  };

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full sm:max-w-lg flex flex-col overflow-y-auto">
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2">
            <PenLine className="h-4 w-4" /> Fill open answers
          </SheetTitle>
          <SheetDescription>
            Questions tagged <span className="font-mono">{tag}</span> with empty answers.
          </SheetDescription>
        </SheetHeader>

        {loading ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground py-6">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading…
          </div>
        ) : openItems.length === 0 ? (
          <p className="text-sm text-muted-foreground py-4">No open-answer items for this tag.</p>
        ) : (
          <ul className="space-y-4 py-2">
            {openItems.map((q) => {
              const id = String(q.id || "");
              const prompt = String(q.prompt || q.question || id);
              return (
                <li key={id} className="rounded-lg border border-border/50 bg-background/40 p-3 space-y-2">
                  <p className="text-sm font-medium leading-snug">{prompt}</p>
                  <p className="text-[10px] font-mono text-muted-foreground">{id}</p>
                  <textarea
                    value={drafts[id] ?? ""}
                    onChange={(e) => setDrafts((d) => ({ ...d, [id]: e.target.value }))}
                    rows={3}
                    className="w-full rounded-md border bg-background px-2 py-1.5 text-sm"
                    placeholder="Expected answer"
                  />
                  <Button
                    size="sm"
                    className="h-7 text-xs"
                    disabled={savingId === id}
                    onClick={() => void saveAnswer(q)}
                  >
                    {savingId === id ? <Loader2 className="h-3 w-3 animate-spin" /> : "Save answer"}
                  </Button>
                </li>
              );
            })}
          </ul>
        )}
      </SheetContent>
    </Sheet>
  );
}
