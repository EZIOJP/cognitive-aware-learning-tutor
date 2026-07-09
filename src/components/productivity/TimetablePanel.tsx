import { useCallback, useEffect, useMemo, useState } from "react";
import { Calendar, ClipboardCopy, ClipboardPaste, Download, Loader2, Upload } from "lucide-react";
import {
  fetchTimetableTemplate,
  fetchTimetables,
  importTimetableText,
  type Timetable,
  type TimetableSlot,
} from "../../api/timetableClient";
import { generateWeekFromTimetable } from "../../api/plannerClient";
import {
  getImportExample,
  IMPORT_EXAMPLE_HINTS,
  IMPORT_EXAMPLE_KINDS,
  IMPORT_EXAMPLE_LABELS,
  type ImportExampleKind,
} from "./importExamples";

const DAY_LABELS: Record<string, string> = {
  mon: "Mon", tue: "Tue", wed: "Wed", thu: "Thu", fri: "Fri", sat: "Sat", sun: "Sun",
};

function slotKey(slot: TimetableSlot): string {
  return `${slot.day}-${slot.start}-${slot.task_index}`;
}

export function TimetablePanel({ onPlannerUpdated }: { onPlannerUpdated?: () => void }) {
  const [timetables, setTimetables] = useState<Timetable[]>([]);
  const [days, setDays] = useState<string[]>(["mon", "tue", "wed", "thu", "fri", "sat", "sun"]);
  const [loading, setLoading] = useState(true);
  const [importing, setImporting] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [activeId, setActiveId] = useState<number | null>(null);
  const [pasteOpen, setPasteOpen] = useState(false);
  const [pasteText, setPasteText] = useState("");
  const [exampleKind, setExampleKind] = useState<ImportExampleKind>("daily");
  const [copyHint, setCopyHint] = useState<string | null>(null);

  const exampleJson = useMemo(() => getImportExample(exampleKind), [exampleKind]);

  const copyExample = async () => {
    try {
      await navigator.clipboard.writeText(exampleJson);
      setCopyHint("Copied to clipboard");
      setTimeout(() => setCopyHint(null), 2000);
    } catch {
      setCopyHint("Copy failed — use Load into editor");
    }
  };

  const loadExampleIntoEditor = () => {
    setPasteText(exampleJson);
    setPasteOpen(true);
    setCopyHint("Loaded into editor — edit and Import");
    setTimeout(() => setCopyHint(null), 2500);
  };

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchTimetables();
      setTimetables(data.timetables);
      if (data.days?.length) setDays(data.days);
      if (data.timetables.length && activeId == null) {
        setActiveId(data.timetables[0].id);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load timetable");
    } finally {
      setLoading(false);
    }
  }, [activeId]);

  useEffect(() => {
    void load();
  }, [load]);

  const active = useMemo(
    () => timetables.find((t) => t.id === activeId) ?? timetables[0] ?? null,
    [timetables, activeId],
  );

  const reportImport = (result: { planner_blocks_created?: number; schedule_type?: string; message?: string }) => {
    if (result.planner_blocks_created) {
      setSuccess(`Imported ${result.schedule_type || "schedule"} — ${result.planner_blocks_created} block(s) added to planner.`);
      onPlannerUpdated?.();
    } else if (result.message) {
      setSuccess(result.message);
      onPlannerUpdated?.();
    } else {
      setSuccess("Timetable imported successfully.");
    }
  };

  const handleImportFile = async (file: File) => {
    setImporting(true);
    setError(null);
    setSuccess(null);
    try {
      const text = await file.text();
      const result = await importTimetableText(text, true);
      reportImport(result);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Import failed");
    } finally {
      setImporting(false);
    }
  };

  const handlePasteImport = async () => {
    if (!pasteText.trim()) return;
    setImporting(true);
    setError(null);
    setSuccess(null);
    try {
      const result = await importTimetableText(pasteText, true);
      reportImport(result);
      setPasteText("");
      setPasteOpen(false);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Import failed — check JSON format");
    } finally {
      setImporting(false);
    }
  };

  const handleDownloadTemplate = async () => {
    try {
      const tpl = await fetchTimetableTemplate();
      const blob = new Blob([JSON.stringify(tpl.daily_example ?? tpl, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "timetable-daily-template.json";
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not download template");
    }
  };

  const handleGenerateWeek = async () => {
    if (!active) return;
    setGenerating(true);
    setError(null);
    try {
      const result = await generateWeekFromTimetable(active.id);
      setSuccess(`Created ${result.created} planner block(s) for this week.`);
      onPlannerUpdated?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Generate week failed");
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="font-semibold flex items-center gap-2">
          <Calendar size={16} className="text-violet-400" />
          Import schedule
        </h2>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            disabled={!active || generating}
            onClick={() => void handleGenerateWeek()}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600/80 hover:bg-emerald-600 text-xs disabled:opacity-50"
          >
            {generating ? <Loader2 size={13} className="animate-spin" /> : <Calendar size={13} />}
            Week → planner
          </button>
          <button
            type="button"
            onClick={() => setPasteOpen((v) => !v)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-xs border border-white/10"
          >
            <ClipboardPaste size={13} />
            Paste JSON
          </button>
          <button
            type="button"
            onClick={() => void handleDownloadTemplate()}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-xs border border-white/10"
          >
            <Download size={13} />
            Daily template
          </button>
          <label className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-violet-600/80 hover:bg-violet-600 text-xs cursor-pointer">
            {importing ? <Loader2 size={13} className="animate-spin" /> : <Upload size={13} />}
            File
            <input
              type="file"
              accept=".json,.txt,application/json,text/plain"
              className="hidden"
              disabled={importing}
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) void handleImportFile(f);
                e.target.value = "";
              }}
            />
          </label>
        </div>
      </div>

      <p className="text-xs text-muted-foreground">
        Paste JSON from ChatGPT or a file — fences and extra text are stripped automatically.
      </p>

      {/* Copyable examples — always visible */}
      <div className="rounded-xl border border-white/10 bg-black/20 p-3 space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
            Example JSON (copy anytime)
          </span>
          <div className="flex flex-wrap rounded-lg border border-white/10 overflow-hidden text-xs">
            {IMPORT_EXAMPLE_KINDS.map((k) => (
              <button
                key={k}
                type="button"
                onClick={() => setExampleKind(k)}
                className={`px-2.5 py-1 ${exampleKind === k ? "bg-white/10" : "text-muted-foreground hover:bg-white/5"}`}
              >
                {IMPORT_EXAMPLE_LABELS[k]}
              </button>
            ))}
          </div>
        </div>
        <p className="text-[11px] text-muted-foreground">{IMPORT_EXAMPLE_HINTS[exampleKind]}</p>
        <pre className="text-[10px] leading-relaxed font-mono bg-black/40 border border-white/5 rounded-lg p-3 max-h-40 overflow-auto whitespace-pre-wrap break-all">
          {exampleJson}
        </pre>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => void copyExample()}
            className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-white/5 hover:bg-white/10 text-xs border border-white/10"
          >
            <ClipboardCopy size={12} />
            Copy example
          </button>
          <button
            type="button"
            onClick={loadExampleIntoEditor}
            className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-violet-600/80 hover:bg-violet-600 text-xs"
          >
            <ClipboardPaste size={12} />
            Load into editor
          </button>
          {copyHint && <span className="text-[11px] text-emerald-400">{copyHint}</span>}
        </div>
      </div>

      {pasteOpen && (
        <div className="space-y-2">
          <textarea
            className="w-full h-40 text-xs font-mono bg-black/30 border border-white/10 rounded-lg p-3 resize-y"
            placeholder="Paste JSON here, or use Copy example / Load into editor above"
            value={pasteText}
            onChange={(e) => setPasteText(e.target.value)}
          />
          <button
            type="button"
            disabled={importing || !pasteText.trim()}
            onClick={() => void handlePasteImport()}
            className="text-xs px-3 py-1.5 rounded-lg bg-violet-600 hover:bg-violet-500 disabled:opacity-50"
          >
            {importing ? "Importing…" : "Import & apply to planner"}
          </button>
        </div>
      )}

      {error && (
        <p className="text-sm text-red-300 bg-red-500/10 border border-red-500/30 rounded-lg px-3 py-2">
          {error}
        </p>
      )}
      {success && (
        <p className="text-sm text-emerald-300 bg-emerald-500/10 border border-emerald-500/30 rounded-lg px-3 py-2">
          {success}
        </p>
      )}

      {loading && !active ? (
        <div className="h-24 rounded-lg bg-white/5 animate-pulse" />
      ) : !active ? (
        <p className="text-sm text-muted-foreground text-center py-6">
          No weekly template stored yet. Paste a daily plan or import a weekly JSON.
        </p>
      ) : (
        <>
          {timetables.length > 1 && (
            <select
              aria-label="Select timetable"
              value={active.id}
              onChange={(e) => setActiveId(Number(e.target.value))}
              className="text-sm bg-black/30 border border-white/10 rounded-lg px-2 py-1"
            >
              {timetables.map((t) => (
                <option key={t.id} value={t.id}>{t.name}</option>
              ))}
            </select>
          )}

          {(active.slots ?? []).length > 0 && (
            <div className="overflow-x-auto max-h-64">
              <table className="w-full text-sm border-collapse min-w-[480px]">
                <thead>
                  <tr className="text-left text-xs text-muted-foreground border-b border-white/10">
                    <th className="py-2 pr-3 w-16">Day</th>
                    <th className="py-2 pr-3 w-28">Time</th>
                    <th className="py-2">Task</th>
                  </tr>
                </thead>
                <tbody>
                  {days.flatMap((day) => {
                    const daySlots = (active.slots ?? []).filter(
                      (s) => s.day.toLowerCase() === day.toLowerCase(),
                    );
                    if (!daySlots.length) return [];
                    return daySlots.map((slot) => {
                      const task = active.tasks[slot.task_index];
                      return (
                        <tr key={slotKey(slot)} className="border-b border-white/5">
                          <td className="py-1.5 pr-3 font-medium">{DAY_LABELS[day] ?? day}</td>
                          <td className="py-1.5 pr-3 tabular-nums text-muted-foreground text-xs">
                            {slot.start}–{slot.end}
                          </td>
                          <td className="py-1.5 text-xs">{slot.title || task?.title}</td>
                        </tr>
                      );
                    });
                  })}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}
