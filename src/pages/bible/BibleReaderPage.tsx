import { useCallback, useEffect, useMemo, useState } from "react";
import { Check, ChevronLeft, ChevronRight, Save } from "lucide-react";
import { useNavigate } from "react-router";
import {
  assignDevotionChapter,
  bibleChapterHeartbeat,
  fetchDevotionToday,
  markDevotionDone,
  saveDevotionNotes,
  saveDevotionPrayer,
  stepDevotionChapter,
  type BibleChapter,
  type DevotionSlot,
  type DevotionTodayPayload,
} from "../../api/bibleClient";
import { formatHoursMinsPair } from "../../utils/formatDuration";
import { invalidateFocusStatusBus } from "../../lib/focusStatusBus";
import { MORNING_UPDATED_EVENT } from "../../components/productivity/ConfirmPlanButton";
import {
  EnforcerUnreachableBanner,
  useEnforcerReachability,
} from "../../components/productivity/EnforcerWriteGate";
import { isFocusDesktopShell } from "../../utils/focusDesktopShell";

type TabId = DevotionSlot;

const COMMON_BOOKS = [
  "Genesis",
  "Exodus",
  "Leviticus",
  "Numbers",
  "Deuteronomy",
  "Joshua",
  "Judges",
  "Ruth",
  "1 Samuel",
  "2 Samuel",
  "1 Kings",
  "2 Kings",
  "1 Chronicles",
  "2 Chronicles",
  "Ezra",
  "Nehemiah",
  "Esther",
  "Job",
  "Psalms",
  "Proverbs",
  "Ecclesiastes",
  "Song of Solomon",
  "Isaiah",
  "Jeremiah",
  "Lamentations",
  "Ezekiel",
  "Daniel",
  "Hosea",
  "Joel",
  "Amos",
  "Obadiah",
  "Jonah",
  "Micah",
  "Nahum",
  "Habakkuk",
  "Zephaniah",
  "Haggai",
  "Zechariah",
  "Malachi",
  "Matthew",
  "Mark",
  "Luke",
  "John",
  "Acts",
  "Romans",
  "1 Corinthians",
  "2 Corinthians",
  "Galatians",
  "Ephesians",
  "Philippians",
  "Colossians",
  "1 Thessalonians",
  "2 Thessalonians",
  "1 Timothy",
  "2 Timothy",
  "Titus",
  "Philemon",
  "Hebrews",
  "James",
  "1 Peter",
  "2 Peter",
  "1 John",
  "2 John",
  "3 John",
  "Jude",
  "Revelation",
];

function VerseList({ chapter }: { chapter: BibleChapter | null }) {
  if (!chapter) {
    return <p className="text-base text-muted-foreground">Chapter not available.</p>;
  }
  return (
    <ol className="space-y-5 text-lg leading-relaxed">
      {(chapter.verses || []).map((v) => (
        <li key={v.number} className="flex gap-4">
          <span className="w-10 shrink-0 text-right text-sm text-muted-foreground tabular-nums pt-1">
            {v.number}
          </span>
          <span className="text-foreground/95">{v.text}</span>
        </li>
      ))}
    </ol>
  );
}

function ReadingPicker({
  slot,
  book,
  chapter,
  onChanged,
}: {
  slot: DevotionSlot;
  book: string;
  chapter: number;
  onChanged: () => void;
}) {
  const [draftBook, setDraftBook] = useState(book);
  const [draftChapter, setDraftChapter] = useState(String(chapter || 1));
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    setDraftBook(book);
    setDraftChapter(String(chapter || 1));
  }, [book, chapter]);

  const apply = async (nextBook: string, nextChapter: number) => {
    setBusy(true);
    setErr(null);
    try {
      await assignDevotionChapter(slot, nextBook, nextChapter);
      onChanged();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const step = async (delta: -1 | 1) => {
    setBusy(true);
    setErr(null);
    try {
      await stepDevotionChapter(slot, delta);
      onChanged();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-x-2 gap-y-1.5">
      <span className="text-[10px] font-medium text-muted-foreground uppercase tracking-wide shrink-0">
        Change reading
      </span>
      <button
        type="button"
        disabled={busy}
        onClick={() => void step(-1)}
        className="inline-flex h-7 w-7 items-center justify-center rounded-md border border-white/10 hover:bg-white/5 disabled:opacity-50"
        aria-label="Previous chapter"
      >
        <ChevronLeft size={14} />
      </button>
      <button
        type="button"
        disabled={busy}
        onClick={() => void step(1)}
        className="inline-flex h-7 w-7 items-center justify-center rounded-md border border-white/10 hover:bg-white/5 disabled:opacity-50"
        aria-label="Next chapter"
      >
        <ChevronRight size={14} />
      </button>
      <label className="inline-flex items-center gap-1.5 text-[11px] text-muted-foreground">
        <span className="sr-only">Book</span>
        <select
          value={draftBook}
          onChange={(e) => setDraftBook(e.target.value)}
          className="rounded-md border border-white/10 bg-black/40 px-2 py-1 text-xs sm:text-sm min-w-[8rem] text-foreground"
          aria-label="Book"
        >
          {COMMON_BOOKS.map((b) => (
            <option key={b} value={b}>
              {b}
            </option>
          ))}
          {!COMMON_BOOKS.includes(draftBook) && draftBook ? (
            <option value={draftBook}>{draftBook}</option>
          ) : null}
        </select>
      </label>
      <label className="inline-flex items-center gap-1.5 text-[11px] text-muted-foreground">
        <span className="sr-only">Chapter</span>
        <input
          type="number"
          min={1}
          value={draftChapter}
          onChange={(e) => setDraftChapter(e.target.value)}
          className="w-14 rounded-md border border-white/10 bg-black/40 px-2 py-1 text-xs sm:text-sm text-foreground"
          aria-label="Chapter"
        />
      </label>
      {slot === "afternoon" ? (
        <button
          type="button"
          disabled={busy}
          onClick={() => void apply("Proverbs", Number(draftChapter) || 1)}
          className="rounded-md border border-amber-500/30 bg-amber-500/10 px-2 py-1 text-[11px] text-amber-100"
        >
          Proverbs
        </button>
      ) : null}
      {slot === "evening" ? (
        <button
          type="button"
          disabled={busy}
          onClick={() => void apply("Psalms", Number(draftChapter) || 1)}
          className="rounded-md border border-sky-500/30 bg-sky-500/10 px-2 py-1 text-[11px] text-sky-100"
        >
          Psalms
        </button>
      ) : null}
      <button
        type="button"
        disabled={busy}
        onClick={() => void apply(draftBook, Math.max(1, Number(draftChapter) || 1))}
        className="rounded-md bg-primary/90 px-2.5 py-1 text-[11px] sm:text-xs font-medium text-primary-foreground disabled:opacity-50"
      >
        Set for today
      </button>
      {err ? <p className="w-full text-xs text-rose-300">{err}</p> : null}
    </div>
  );
}

function EditablePrayer({
  slot,
  title,
  value,
  onSaved,
}: {
  slot: DevotionSlot;
  title: string;
  value: string;
  onSaved: () => void;
}) {
  const [draft, setDraft] = useState(value);
  const [saving, setSaving] = useState(false);
  useEffect(() => setDraft(value), [value]);

  const save = async (reset = false) => {
    setSaving(true);
    try {
      await saveDevotionPrayer(slot, draft, reset);
      onSaved();
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="rounded-xl border border-violet-500/20 bg-violet-500/5 px-4 py-3 space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-medium text-violet-100">{title}</h3>
        <div className="flex gap-1.5">
          <button
            type="button"
            disabled={saving}
            onClick={() => void save(false)}
            className="inline-flex items-center gap-1 rounded-md border border-white/10 px-2 py-1 text-[11px] hover:bg-white/5 disabled:opacity-50"
          >
            <Save size={11} />
            Save prayer
          </button>
          <button
            type="button"
            disabled={saving}
            onClick={() => void save(true)}
            className="rounded-md border border-white/10 px-2 py-1 text-[11px] hover:bg-white/5 disabled:opacity-50"
          >
            Reset default
          </button>
        </div>
      </div>
      <textarea
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        rows={8}
        className="w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm resize-y leading-relaxed"
      />
    </div>
  );
}

function JournalField({
  slot,
  value,
  onSaved,
}: {
  slot: DevotionSlot;
  value: string;
  onSaved: () => void;
}) {
  const [draft, setDraft] = useState(value);
  const [saving, setSaving] = useState(false);
  useEffect(() => setDraft(value), [value]);

  const save = async () => {
    setSaving(true);
    try {
      await saveDevotionNotes(slot, draft);
      onSaved();
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-2 rounded-xl border border-teal-500/20 bg-teal-500/5 px-4 py-3">
      <label className="text-sm font-medium text-teal-100">Journal</label>
      <p className="text-[11px] text-muted-foreground">
        Saved with this devotion slot and mirrored into Focus Journal.
      </p>
      <textarea
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        rows={4}
        placeholder="What stood out? What will you carry forward?"
        className="w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm resize-y"
      />
      <button
        type="button"
        onClick={() => void save()}
        disabled={saving}
        className="inline-flex items-center gap-1.5 rounded-md border border-white/10 px-3 py-1.5 text-xs hover:bg-white/5 disabled:opacity-50"
      >
        <Save size={12} />
        {saving ? "Saving…" : "Save journal"}
      </button>
    </div>
  );
}

export function BibleReaderPage() {
  const navigate = useNavigate();
  const reach = useEnforcerReachability();
  const writesLocked =
    isFocusDesktopShell() && (reach === "down" || reach === "no_bridge");
  const [data, setData] = useState<DevotionTodayPayload | null>(null);
  const [tab, setTab] = useState<TabId>("morning");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    const payload = await fetchDevotionToday("web");
    setData(payload);
    return payload;
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    void load()
      .then(() => {
        if (!cancelled) setError(null);
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [load]);

  const today = data?.today_chapter;
  const goal = data?.chapter_goal;
  const gate = data?.gate as
    | { day_unlimited?: boolean; productive_minutes?: number; daily_goal_minutes?: number; unlock_mode?: string }
    | undefined;

  const activeBookChapter = useMemo(() => {
    if (!data) return { book: "Genesis", chapter: 1 };
    if (tab === "morning") {
      return { book: today?.book || "Genesis", chapter: today?.chapter || 1 };
    }
    if (tab === "afternoon") {
      return { book: data.afternoon?.book || "Proverbs", chapter: data.afternoon?.chapter || 1 };
    }
    return { book: data.evening?.book || "Psalms", chapter: data.evening?.chapter || 1 };
  }, [data, tab, today?.book, today?.chapter]);

  useEffect(() => {
    // Heartbeat is a write — skip when pipe is down so Bible open stays mirror-only.
    if (writesLocked) return;
    if (tab !== "morning" || !today?.book || !today?.chapter) return;
    const book = today.book;
    const chapter = today.chapter;
    const tick = () => {
      void bibleChapterHeartbeat(book, chapter, document.visibilityState === "visible", 1).catch(
        () => undefined,
      );
    };
    tick();
    const id = window.setInterval(tick, 60_000);
    return () => window.clearInterval(id);
  }, [tab, today?.book, today?.chapter, writesLocked]);

  const onMarkDone = async (slot: TabId) => {
    if (!data) return;
    const today = (() => {
      const d = new Date();
      return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
    })();
    const mirrorIsToday = !data.day || data.day === today;
    const currentlyDone =
      slot === "morning" ? Boolean(data.today_chapter?.done) : Boolean(data[slot]?.done);
    // Stale yesterday mirrors show done=true; never treat that as a toggle-undo for today.
    const nextDone = mirrorIsToday ? !currentlyDone : true;
    try {
      await markDevotionDone(slot, nextDone);
      await load();
      // SoftLand goals update immediately; dayLoop bus must refresh or MorningBibleOverlay
      // keeps a full-screen lock when leaving /bible.
      invalidateFocusStatusBus({ pipe: true });
      window.dispatchEvent(new Event(MORNING_UPDATED_EVENT));
      setError(null);
      // Morning unlock → plan tab (hash links break Focus router).
      if (slot === "morning" && nextDone) {
        navigate("/productivity?tab=plan");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const tabs: { id: TabId; label: string; done: boolean }[] = [
    { id: "morning", label: "Morning", done: Boolean(data?.today_chapter?.done) },
    { id: "afternoon", label: "Afternoon", done: Boolean(data?.afternoon?.done) },
    { id: "evening", label: "Evening", done: Boolean(data?.evening?.done) },
  ];

  const morningTitle = today?.label || "Today's chapter";
  const afternoonTitle = data?.afternoon?.label || "Proverbs";
  const eveningTitle = data?.evening?.label || "Psalms";

  const tabTitle =
    tab === "morning" ? morningTitle : tab === "afternoon" ? afternoonTitle : eveningTitle;

  const markDoneLabel =
    tab === "morning"
      ? data?.today_chapter?.done
        ? "Chapter done"
        : "Mark chapter done"
      : data?.[tab]?.done
        ? "Done today"
        : `Mark ${tab} done`;

  const isDone =
    tab === "morning" ? Boolean(data?.today_chapter?.done) : Boolean(data?.[tab]?.done);

  const prayerTitle =
    tab === "morning"
      ? "The Lord's Prayer"
      : tab === "afternoon"
        ? "Afternoon prayer"
        : "Evening prayer";

  const prayerText =
    tab === "morning"
      ? data?.morning?.lords_prayer || data?.morning?.prayer || ""
      : tab === "afternoon"
        ? data?.afternoon?.prayer || ""
        : data?.evening?.prayer || data?.evening?.lords_prayer || data?.evening?.worship_opening || "";

  const journalText =
    tab === "morning"
      ? data?.morning?.journal || data?.morning?.notes || ""
      : tab === "afternoon"
        ? data?.afternoon?.journal || data?.afternoon?.notes || ""
        : data?.evening?.journal || data?.evening?.notes || "";

  const chapterBody =
    tab === "morning"
      ? data?.morning_chapter
      : tab === "afternoon"
        ? data?.afternoon_chapter
        : data?.evening_chapter;

  return (
    <div className="flex h-[calc(100vh-4rem)] flex-col gap-3 p-4 sm:p-6">
      {writesLocked ? <EnforcerUnreachableBanner reachability={reach} /> : null}
      <div className="gloss-panel rounded-xl px-3 py-2 sm:px-4 sm:py-2.5 shrink-0 space-y-2">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
          <h1 className="text-base sm:text-lg font-semibold tracking-tight whitespace-nowrap shrink-0">
            Devotion
          </h1>

          <div
            className="flex gap-0.5 rounded-lg bg-black/25 p-0.5 shrink-0"
            role="tablist"
            aria-label="Devotion time of day"
          >
            {tabs.map((t) => (
              <button
                key={t.id}
                type="button"
                role="tab"
                aria-selected={tab === t.id}
                onClick={() => setTab(t.id)}
                className={`rounded-md px-2.5 py-1 text-xs sm:text-sm font-medium transition-colors ${
                  tab === t.id
                    ? "bg-white/12 text-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground hover:bg-white/5"
                }`}
              >
                {t.label}
                {t.done ? " ✓" : ""}
              </button>
            ))}
          </div>

          <div className="min-w-0 flex-1 basis-[8rem]">
            <p className="text-sm font-medium truncate" title={tabTitle}>
              {tabTitle}
            </p>
          </div>

          <div className="flex items-center gap-2 shrink-0 ml-auto">
            <span className="rounded-md bg-black/30 px-2 py-1 text-[11px] sm:text-xs tabular-nums text-muted-foreground">
              Ch{" "}
              <strong className="text-foreground">
                {goal?.done ?? 0}/{goal?.target ?? 1}
              </strong>
              {goal?.met ? " ✓" : ""}
            </span>
            <span className="rounded-md bg-black/30 px-2 py-1 text-[11px] sm:text-xs tabular-nums text-muted-foreground hidden sm:inline">
              Study{" "}
              <strong className="text-foreground">
                {formatHoursMinsPair(gate?.productive_minutes, gate?.daily_goal_minutes)}
              </strong>
            </span>
            <button
              type="button"
              onClick={() => void onMarkDone(tab)}
              disabled={loading || !data || writesLocked}
              title={writesLocked ? "Needs running enforcer" : undefined}
              className={`inline-flex items-center gap-1 rounded-md px-2.5 py-1.5 text-xs sm:text-sm font-medium disabled:opacity-50 shrink-0 ${
                isDone
                  ? "bg-emerald-500/20 text-emerald-100 border border-emerald-400/40"
                  : "bg-primary/90 text-primary-foreground"
              }`}
            >
              <Check className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">{markDoneLabel}</span>
              <span className="sm:hidden">{isDone ? "Done" : "Mark"}</span>
            </button>
          </div>
        </div>

        {data ? (
          <div className="border-t border-white/10 pt-2">
            <ReadingPicker
              slot={tab}
              book={activeBookChapter.book}
              chapter={activeBookChapter.chapter}
              onChanged={() => void load().then(() => setError(null))}
            />
          </div>
        ) : null}
      </div>

      {error && <p className="text-sm text-rose-300 shrink-0">{error}</p>}
      {writesLocked && data ? (
        <p className="text-[11px] text-amber-100/80 shrink-0">
          Reading from SQLite mirror + WEB corpus. Mark done / change reading need enforcer.
        </p>
      ) : null}

      {data?.today_chapter?.done && tab === "morning" && (
        <div className="rounded-lg border border-teal-500/30 bg-teal-500/10 px-3 py-2 text-xs sm:text-sm text-teal-100 shrink-0">
          Morning done. SoftLand is unlocked for planning.{" "}
          <button
            type="button"
            className="underline"
            onClick={() => navigate("/productivity?tab=plan")}
          >
            Confirm plan
          </button>
        </div>
      )}

      <div className="min-h-0 flex-1 overflow-y-auto rounded-xl border border-white/10 bg-black/40 px-4 sm:px-6 py-4 sm:py-5 space-y-5">
        {loading && !data ? (
          <p className="text-base text-muted-foreground">Loading devotion…</p>
        ) : data ? (
          <>
            <VerseList chapter={chapterBody} />
            {!chapterBody?.verses?.length ? (
              <p className="text-sm text-amber-100/85">
                Chapter text missing from{" "}
                <code className="text-xs">data/productivity/bible/structured/web.json</code>
                . Confirm calt_focus mapped calt-bible.app, then Reload UI.
              </p>
            ) : null}
            <EditablePrayer
              slot={tab}
              title={prayerTitle}
              value={prayerText}
              onSaved={() => void load()}
            />
            <JournalField slot={tab} value={journalText} onSaved={() => void load()} />
          </>
        ) : (
          <p className="text-base text-muted-foreground">
            Could not load devotion. Start the enforcer (tray Run stack / CALT Enforcer task), then
            reopen Bible.
          </p>
        )}
      </div>
    </div>
  );
}
