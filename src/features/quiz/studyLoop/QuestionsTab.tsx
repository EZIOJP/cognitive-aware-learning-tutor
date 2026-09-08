import { useEffect, useMemo, useRef, useState } from "react";
import { Download, Loader2, PenLine, Upload } from "lucide-react";
import { toast } from "sonner";
import { Button } from "../../../app/components/ui/button";
import {
  fetchStudyLoopQuestions,
  patchStudyLoopQuestion,
} from "../../../api/globalQuizClient";
import { QuestionEditor } from "./QuestionEditor";

/** Light rules object matching canvas QUESTION_PACK_RULES. */
export const QUESTION_PACK_RULES = {
  schema_version: 1,
  completeness: {
    math_mcq_coding: "non-empty answer required",
    open: "answer + (solution_steps OR explanation) required",
  },
  generation: {
    grounded: "Prefer note section for topic_id; no invented curriculum facts",
    kinds: ["mcq", "math", "open", "coding", "coding_mcq"],
    tags: "Always include note topic id (L*/MT*) plus free tags",
    speed_fluency:
      "Only set speed_fluency / recall_fact on pure fact cells — not procedural",
  },
  refinement: {
    ai_fill:
      "Fill empty answer, solution_steps, explanation; never overwrite non-empty fields unless force=true",
    verify: "Human must verify AI drafts before re-import",
    export_roundtrip: "Export → edit/refine → Import merge by id",
  },
};

type BankQuestion = Record<string, unknown> & {
  id?: string;
  prompt?: string;
  question?: string;
  expected_answer?: string;
  answer?: string;
  solution_steps?: string;
  explanation?: string;
  kind?: string;
  tags?: string[];
  note_topic_ids?: string[];
  topic?: string;
  domain?: string;
  open?: boolean;
};

type StatusFilter = "all" | "complete" | "incomplete";

type Props = {
  focusTag?: string | null;
};

function questionComplete(q: BankQuestion): boolean {
  const answer = String(q.expected_answer || q.answer || "").trim();
  const steps = String(q.solution_steps || "").trim();
  const explanation = String(q.explanation || "").trim();
  const kind = String(q.kind || "").toLowerCase();
  if (kind === "open" || q.open === true) {
    return Boolean(answer) && Boolean(steps || explanation);
  }
  return Boolean(answer);
}

function promptOf(q: BankQuestion): string {
  return String(q.prompt || q.question || q.id || "—");
}

function topicKey(q: BankQuestion): string {
  const ntid = Array.isArray(q.note_topic_ids) ? q.note_topic_ids[0] : null;
  if (typeof ntid === "string" && ntid.trim()) return ntid.trim();
  if (typeof q.topic === "string" && q.topic.trim()) return q.topic.trim();
  const tags = Array.isArray(q.tags) ? q.tags : [];
  const mt = tags.find((t) => /^MT\d+-T/i.test(String(t)) || /^L\d+-T/i.test(String(t)));
  if (mt) return String(mt);
  return "untagged";
}

function parseImportPayload(raw: string): BankQuestion[] {
  const parsed: unknown = JSON.parse(raw);
  if (Array.isArray(parsed)) return parsed as BankQuestion[];
  if (parsed && typeof parsed === "object") {
    const obj = parsed as Record<string, unknown>;
    if (Array.isArray(obj.questions)) return obj.questions as BankQuestion[];
    if (typeof obj.id === "string") return [parsed as BankQuestion];
  }
  return [];
}

function downloadJson(filename: string, data: unknown) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function QuestionsTab({ focusTag }: Props) {
  const [items, setItems] = useState<BankQuestion[]>([]);
  const [loading, setLoading] = useState(false);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [editorOpen, setEditorOpen] = useState(false);
  const [editorTag, setEditorTag] = useState(focusTag || "");
  const [savingId, setSavingId] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const load = async () => {
    setLoading(true);
    try {
      const res = await fetchStudyLoopQuestions(
        focusTag ? { tag: focusTag } : undefined
      );
      setItems((res.items || []) as BankQuestion[]);
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Failed to load questions");
      setItems([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reload when focus tag changes
  }, [focusTag]);

  const filtered = useMemo(() => {
    return items.filter((q) => {
      const done = questionComplete(q);
      if (statusFilter === "complete") return done;
      if (statusFilter === "incomplete") return !done;
      return true;
    });
  }, [items, statusFilter]);

  const groups = useMemo(() => {
    const map = new Map<string, BankQuestion[]>();
    for (const q of filtered) {
      const key = topicKey(q);
      const list = map.get(key) ?? [];
      list.push(q);
      map.set(key, list);
    }
    return Array.from(map.entries()).sort((a, b) => a[0].localeCompare(b[0]));
  }, [filtered]);

  const completeN = items.filter(questionComplete).length;
  const incompleteN = items.length - completeN;

  const exportFiltered = () => {
    downloadJson("study-loop-questions.json", {
      schema_version: 1,
      scope: "filtered",
      group_by: "topic",
      group_key: statusFilter,
      rules: QUESTION_PACK_RULES,
      questions: filtered,
    });
    toast.success(`Exported ${filtered.length} question(s)`);
  };

  const onImportFile = async (file: File) => {
    try {
      const text = await file.text();
      const list = parseImportPayload(text);
      if (!list.length) {
        toast.error("No questions in import file");
        return;
      }
      let patched = 0;
      for (const q of list) {
        const id = String(q.id || "").trim();
        if (!id) continue;
        const answer = String(q.expected_answer || q.answer || "");
        try {
          await patchStudyLoopQuestion(id, {
            expected_answer: answer,
            answer,
            solution_steps: q.solution_steps,
            explanation: q.explanation,
          });
          patched += 1;
        } catch {
          /* skip rows that cannot patch */
        }
      }
      toast.success(`Import applied to ${patched} question(s)`);
      await load();
    } catch {
      toast.error("Import failed — need JSON pack or questions[]");
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold">Questions</h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Focus: {focusTag || "all tags"} · {completeN} complete · {incompleteN} incomplete
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <input
            ref={fileRef}
            type="file"
            accept="application/json,.json"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) void onImportFile(f);
              e.target.value = "";
            }}
          />
          <Button
            size="sm"
            variant="secondary"
            className="gap-1"
            onClick={() => fileRef.current?.click()}
          >
            <Upload className="h-3.5 w-3.5" /> Import
          </Button>
          <Button size="sm" variant="outline" className="gap-1" onClick={exportFiltered}>
            <Download className="h-3.5 w-3.5" /> Export ({filtered.length})
          </Button>
          <Button
            size="sm"
            variant="ghost"
            className="gap-1"
            disabled={!focusTag}
            onClick={() => {
              setEditorTag(focusTag || "");
              setEditorOpen(true);
            }}
          >
            <PenLine className="h-3.5 w-3.5" /> Edit answers
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <div className="rounded-xl border border-border/50 bg-background/40 p-3">
          <p className="text-lg font-semibold tabular-nums">{items.length}</p>
          <p className="text-[11px] text-muted-foreground">In bank</p>
        </div>
        <div className="rounded-xl border border-border/50 bg-background/40 p-3">
          <p className="text-lg font-semibold tabular-nums">{completeN}</p>
          <p className="text-[11px] text-muted-foreground">Complete</p>
        </div>
        <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-3">
          <p className="text-lg font-semibold tabular-nums">{incompleteN}</p>
          <p className="text-[11px] text-muted-foreground">Incomplete</p>
        </div>
      </div>

      <div className="flex flex-wrap gap-1.5">
        {(["all", "complete", "incomplete"] as const).map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => setStatusFilter(s)}
            className={`rounded-full px-2.5 py-0.5 text-[11px] border transition ${
              statusFilter === s
                ? "bg-primary/15 text-primary border-primary/40 font-medium"
                : "border-border/60 text-muted-foreground"
            }`}
          >
            {s}
          </button>
        ))}
        <Button size="sm" variant="ghost" className="h-7 text-xs ml-auto" onClick={() => void load()}>
          Refresh
        </Button>
      </div>

      {loading ? (
        <div className="flex items-center gap-2 text-sm text-muted-foreground py-6">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading questions…
        </div>
      ) : groups.length === 0 ? (
        <p className="text-sm text-muted-foreground py-4">No questions match this filter.</p>
      ) : (
        <div className="space-y-4">
          {groups.map(([groupKey, qs]) => {
            const doneN = qs.filter(questionComplete).length;
            return (
              <div key={groupKey} className="gloss-panel rounded-xl p-4 space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h3 className="text-sm font-semibold font-mono">{groupKey}</h3>
                  <div className="flex items-center gap-2">
                    <span className="text-[11px] text-muted-foreground">
                      {doneN}/{qs.length}
                    </span>
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-7 text-xs"
                      onClick={() => {
                        setEditorTag(groupKey === "untagged" ? focusTag || "" : groupKey);
                        setEditorOpen(true);
                      }}
                    >
                      Edit
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-7 text-xs"
                      onClick={() =>
                        downloadJson(`questions-${groupKey}.json`, {
                          schema_version: 1,
                          scope: "group",
                          group_by: "topic",
                          group_key: groupKey,
                          rules: QUESTION_PACK_RULES,
                          questions: qs,
                        })
                      }
                    >
                      Export
                    </Button>
                  </div>
                </div>
                <ul className="divide-y rounded-lg border border-border/50 overflow-hidden">
                  {qs.slice(0, 40).map((q) => {
                    const id = String(q.id || "");
                    const done = questionComplete(q);
                    return (
                      <li
                        key={id || promptOf(q)}
                        className="flex items-center justify-between gap-2 px-3 py-2 text-sm bg-background/40"
                      >
                        <div className="min-w-0">
                          <p className="truncate">{promptOf(q)}</p>
                          <p className="text-[10px] text-muted-foreground mt-0.5">
                            {String(q.kind || "q")} · {done ? "complete" : "incomplete"}
                          </p>
                        </div>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-7 text-xs shrink-0"
                          disabled={!id || savingId === id}
                          onClick={async () => {
                            if (!id) return;
                            setSavingId(id);
                            try {
                              const answer = String(q.expected_answer || q.answer || "").trim();
                              if (!answer) {
                                setEditorTag(topicKey(q) === "untagged" ? focusTag || "" : topicKey(q));
                                setEditorOpen(true);
                                return;
                              }
                              await patchStudyLoopQuestion(id, {
                                expected_answer: answer,
                                answer,
                              });
                              toast.success("Saved");
                            } catch (err: unknown) {
                              toast.error(err instanceof Error ? err.message : "Save failed");
                            } finally {
                              setSavingId(null);
                            }
                          }}
                        >
                          {done ? "OK" : "Fill"}
                        </Button>
                      </li>
                    );
                  })}
                </ul>
              </div>
            );
          })}
        </div>
      )}

      {editorTag ? (
        <QuestionEditor tag={editorTag} open={editorOpen} onOpenChange={setEditorOpen} />
      ) : null}
    </div>
  );
}
