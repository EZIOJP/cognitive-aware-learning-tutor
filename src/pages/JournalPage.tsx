import { useCallback, useEffect, useState } from "react";
import { CheckCircle2, PenLine } from "lucide-react";
import { ScrollPage } from "../components/layout/ScrollPage";
import {
  fetchJournalSummary,
  saveJournalEntry,
  type JournalSummary,
} from "../api/journalClient";

export function JournalPage() {
  const [summary, setSummary] = useState<JournalSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [journalTitle, setJournalTitle] = useState("");
  const [journalContent, setJournalContent] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const s = await fetchJournalSummary();
      setSummary(s);
      if (s.journal_entry) {
        setJournalTitle(s.journal_entry.title || "");
        setJournalContent(s.journal_entry.content);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const handleSave = async () => {
    if (!journalContent.trim()) return;
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      await saveJournalEntry({
        title: journalTitle.trim() || undefined,
        content: journalContent.trim(),
      });
      setSuccess("Journal saved.");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save");
    } finally {
      setSaving(false);
    }
  };

  return (
    <ScrollPage>
      <div className="space-y-5">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2 text-foreground">
            <PenLine size={22} className="text-amber-400" />
            My Journal
          </h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Your private daily journal
          </p>
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
        {success && (
          <p className="text-sm text-emerald-300 bg-emerald-500/10 border border-emerald-500/30 rounded-lg px-3 py-2">{success}</p>
        )}

        {loading ? (
          <div className="h-48 rounded-xl bg-white/5 animate-pulse" />
        ) : (
          <section className="space-y-3 rounded-2xl border border-white/10 bg-white/[0.03] p-5">
            <input
              className="w-full text-sm bg-black/30 border border-white/10 rounded-lg px-3 py-2 text-foreground"
              placeholder="Title (optional)"
              value={journalTitle}
              onChange={(e) => setJournalTitle(e.target.value)}
            />
            <textarea
              className="w-full h-64 text-sm bg-black/30 border border-white/10 rounded-lg p-3 resize-y leading-relaxed text-foreground"
              placeholder="How was your day? Gratitude, struggles, prayers, plans for tomorrow…"
              value={journalContent}
              onChange={(e) => setJournalContent(e.target.value)}
            />
            <button
              type="button"
              disabled={saving || !journalContent.trim()}
              onClick={() => void handleSave()}
              className="text-sm px-4 py-2 rounded-lg bg-amber-600/90 hover:bg-amber-600 disabled:opacity-50 text-white"
            >
              {saving ? "Saving…" : summary?.journal_written ? "Update today's entry" : "Save today's entry"}
            </button>
          </section>
        )}
      </div>
    </ScrollPage>
  );
}
