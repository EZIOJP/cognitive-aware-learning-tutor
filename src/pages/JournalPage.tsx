import { useCallback, useEffect, useRef, useState } from "react";
import { CalendarDays, CheckCircle2, Clock, PenLine } from "lucide-react";
import { ScrollPage } from "../components/layout/ScrollPage";
import {
  fetchJournalLog,
  fetchJournalSummary,
  saveJournalEntry,
  type JournalLogEntry,
  type JournalSummary,
} from "../api/journalClient";
import { useEaster } from "../easter";

const AUTOSAVE_MS = 1500;

function formatDateLabel(day: string): string {
  const d = new Date(`${day}T00:00:00`);
  return new Intl.DateTimeFormat(undefined, {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  }).format(d);
}

function formatUpdatedAt(value?: string | null): string {
  if (!value) return "not synced";
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

function formatSavedClock(d = new Date()): string {
  return new Intl.DateTimeFormat(undefined, {
    hour: "numeric",
    minute: "2-digit",
  }).format(d);
}

function localDayString(d = new Date()): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export function JournalPage() {
  const { burst } = useEaster();
  const [summary, setSummary] = useState<JournalSummary | null>(null);
  const [logEntries, setLogEntries] = useState<JournalLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);
  const [journalTitle, setJournalTitle] = useState("");
  const [journalContent, setJournalContent] = useState("");
  const todayDay = localDayString();
  const titleRef = useRef(journalTitle);
  const contentRef = useRef(journalContent);
  const dirtyRef = useRef(false);
  const savingRef = useRef(false);
  titleRef.current = journalTitle;
  contentRef.current = journalContent;
  dirtyRef.current = dirty;
  savingRef.current = saving;

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const s = await fetchJournalSummary(todayDay);
      setSummary(s);
      fetchJournalLog(30)
        .then(setLogEntries)
        .catch(() => setLogEntries([]));
      if (s.journal_entry) {
        setJournalTitle(s.journal_entry.title || "");
        setJournalContent(s.journal_entry.content);
        if (s.journal_entry.updated_at) {
          setSavedAt(formatUpdatedAt(s.journal_entry.updated_at));
        }
      } else {
        setJournalTitle("");
        setJournalContent("");
        setSavedAt(null);
      }
      setDirty(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, [todayDay]);

  useEffect(() => {
    void load();
  }, [load]);

  const persist = useCallback(async (opts?: { silent?: boolean }) => {
    const content = contentRef.current.trim();
    if (!content || savingRef.current) return false;
    savingRef.current = true;
    setSaving(true);
    if (!opts?.silent) setError(null);
    try {
      await saveJournalEntry({
        title: titleRef.current.trim() || undefined,
        content,
        entry_date: todayDay,
      });
      setDirty(false);
      dirtyRef.current = false;
      setSavedAt(formatSavedClock());
      setSummary((prev) =>
        prev
          ? {
              ...prev,
              journal_written: true,
              journal_entry: {
                ...(prev.journal_entry || { id: 0, entry_date: todayDay, content }),
                title: titleRef.current.trim() || undefined,
                content,
                updated_at: new Date().toISOString(),
              },
            }
          : prev,
      );
      return true;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save");
      return false;
    } finally {
      savingRef.current = false;
      setSaving(false);
    }
  }, [todayDay]);

  // Debounced autosave
  useEffect(() => {
    if (!dirty || loading) return;
    if (!journalContent.trim()) return;
    const t = window.setTimeout(() => {
      void persist({ silent: true });
    }, AUTOSAVE_MS);
    return () => window.clearTimeout(t);
  }, [dirty, journalContent, journalTitle, loading, persist]);

  // Save on blur / unload
  useEffect(() => {
    const onVis = () => {
      if (document.visibilityState === "hidden" && dirtyRef.current) {
        void persist({ silent: true });
      }
    };
    const onBeforeUnload = (e: BeforeUnloadEvent) => {
      if (!dirtyRef.current) return;
      void persist({ silent: true });
      e.preventDefault();
      e.returnValue = "";
    };
    document.addEventListener("visibilitychange", onVis);
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => {
      document.removeEventListener("visibilitychange", onVis);
      window.removeEventListener("beforeunload", onBeforeUnload);
    };
  }, [persist]);

  const markDirty = () => {
    setDirty(true);
    dirtyRef.current = true;
  };

  const activeDay = summary?.day ?? todayDay;
  const todayLabel = formatDateLabel(activeDay);
  const previousEntries = logEntries.filter((entry) => entry.entry_date !== activeDay);
  const statusLabel = saving
    ? "Saving…"
    : dirty
      ? "Unsaved changes"
      : savedAt
        ? `Saved ${savedAt}`
        : summary?.journal_entry?.updated_at
          ? `Updated ${formatUpdatedAt(summary.journal_entry.updated_at)}`
          : "Not saved yet";

  return (
    <ScrollPage>
      <div className="space-y-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2 text-foreground">
              <PenLine size={22} className="text-amber-400" />
              My Journal
            </h1>
            <p className="text-sm text-muted-foreground mt-0.5">
              Your private daily journal — autosaves while you type
            </p>
          </div>
          <div className="inline-flex items-center gap-2 rounded-full border border-amber-500/25 bg-amber-500/10 px-3 py-1 text-xs text-amber-100">
            <CalendarDays size={14} className="text-amber-300" />
            {todayLabel}
          </div>
        </div>

        {summary?.journal_written && (
          <span className="inline-flex items-center gap-1 text-xs text-emerald-400">
            <CheckCircle2 size={14} />
            Written today
          </span>
        )}

        {error && (
          <p className="text-sm text-red-300 bg-red-500/10 border border-red-500/30 rounded-lg px-3 py-2">{error}</p>
        )}

        {loading ? (
          <div className="h-48 rounded-xl bg-white/5 animate-pulse" />
        ) : (
          <section className="space-y-3 rounded-2xl border border-white/10 bg-white/[0.03] p-5">
            <div className="flex items-center justify-between gap-3 text-xs text-muted-foreground">
              <span>Today&apos;s entry</span>
              <span className="inline-flex items-center gap-1 tabular-nums">
                <Clock size={12} />
                {statusLabel}
              </span>
            </div>
            <input
              className="w-full text-sm bg-black/30 border border-white/10 rounded-lg px-3 py-2 text-foreground"
              placeholder="Title (optional)"
              value={journalTitle}
              onChange={(e) => {
                setJournalTitle(e.target.value);
                markDirty();
              }}
              onBlur={() => {
                if (dirtyRef.current) void persist({ silent: true });
              }}
            />
            <textarea
              className="w-full h-64 text-sm bg-black/30 border border-white/10 rounded-lg p-3 resize-y leading-relaxed text-foreground"
              placeholder="How was your day? Gratitude, struggles, prayers, plans for tomorrow…"
              value={journalContent}
              onChange={(e) => {
                const v = e.target.value;
                const prev = journalContent;
                setJournalContent(v);
                markDirty();
                if (/\bgrateful\b/i.test(v) && !/\bgrateful\b/i.test(prev)) {
                  burst("glow");
                }
              }}
              onBlur={() => {
                if (dirtyRef.current) void persist({ silent: true });
              }}
            />
            <button
              type="button"
              disabled={saving || !journalContent.trim() || !dirty}
              onClick={() => void persist()}
              className="text-sm px-4 py-2 rounded-lg bg-amber-600/90 hover:bg-amber-600 disabled:opacity-50 text-white"
            >
              {saving ? "Saving…" : dirty ? "Save now" : "Saved"}
            </button>
          </section>
        )}

        {!loading && (
          <section className="rounded-2xl border border-white/10 bg-white/[0.03] p-5 space-y-3">
            <div>
              <h2 className="text-sm font-semibold">Previous entries log</h2>
              <p className="text-xs text-muted-foreground mt-0.5">
                Shows only metadata. Journal content stays hidden unless you open that day.
              </p>
            </div>

            {previousEntries.length === 0 ? (
              <p className="text-sm text-muted-foreground py-4">No previous journal entries yet.</p>
            ) : (
              <ul className="space-y-2">
                {previousEntries.map((entry) => (
                  <li
                    key={entry.id}
                    className="rounded-xl border border-white/10 bg-black/20 px-3 py-2.5 flex flex-wrap items-center justify-between gap-2"
                  >
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-foreground truncate">
                        {formatDateLabel(entry.entry_date)}
                      </p>
                      <p className="text-xs text-muted-foreground truncate">
                        {entry.title?.trim() || "Untitled entry"}
                      </p>
                    </div>
                    <div className="text-[11px] text-muted-foreground tabular-nums text-right">
                      <p>{entry.word_count} words</p>
                      <p>Updated {formatUpdatedAt(entry.updated_at)}</p>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>
        )}
      </div>
    </ScrollPage>
  );
}
