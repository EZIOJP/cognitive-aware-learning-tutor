import { useCallback, useEffect, useState } from "react";
import { Check, Save } from "lucide-react";
import {
  bibleChapterHeartbeat,
  fetchDevotionToday,
  markDevotionDone,
  saveDevotionNotes,
  type BibleChapter,
  type DevotionSlot,
  type DevotionTodayPayload,
} from "../../api/bibleClient";
import { formatHoursMinsPair } from "../../utils/formatDuration";

type TabId = DevotionSlot;

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

function PrayerBlock({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-xl border border-violet-500/20 bg-violet-500/5 px-4 py-3 space-y-2">
      <h3 className="text-sm font-medium text-violet-100">{title}</h3>
      <p className="text-sm text-foreground/90 whitespace-pre-wrap leading-relaxed">{body}</p>
    </div>
  );
}

function NotesField({
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
    <div className="space-y-2">
      <label className="text-xs text-muted-foreground">Your notes / reflections</label>
      <textarea
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        rows={3}
        placeholder="What stood out? What will you carry into the day?"
        className="w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm resize-y"
      />
      <button
        type="button"
        onClick={() => void save()}
        disabled={saving}
        className="inline-flex items-center gap-1.5 rounded-md border border-white/10 px-3 py-1.5 text-xs hover:bg-white/5 disabled:opacity-50"
      >
        <Save size={12} />
        {saving ? "Saving…" : "Save notes"}
      </button>
    </div>
  );
}

export function BibleReaderPage() {
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

  useEffect(() => {
    if (tab !== "morning" || !today?.book || !today?.chapter) return;
    const book = today.book;
    const chapter = today.chapter;
    const tick = () => {
      void bibleChapterHeartbeat(book, chapter, document.visibilityState === "visible", 1).catch(
        () => undefined,
      );
    };
    tick();
    const id = window.setInterval(tick, 20_000);
    return () => window.clearInterval(id);
  }, [tab, today?.book, today?.chapter]);

  const onMarkDone = async (slot: TabId) => {
    if (!data) return;
    const currentlyDone =
      slot === "morning"
        ? Boolean(data.today_chapter?.done)
        : Boolean(data[slot]?.done);
    try {
      await markDevotionDone(slot, !currentlyDone);
      await load();
      setError(null);
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
    tab === "morning"
      ? morningTitle
      : tab === "afternoon"
        ? afternoonTitle
        : `${eveningTitle} + ${data?.evening?.worship_title || "worship"}`;

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

  const slotHint =
    tab === "morning"
      ? data?.morning?.note
      : tab === "afternoon"
        ? data?.afternoon?.note
        : data?.evening?.note;

  return (
    <div className="flex h-[calc(100vh-4rem)] flex-col gap-3 p-4 sm:p-6">
      {/* Single-row toolbar: title · tabs · reading · stats · mark done */}
      <div className="gloss-panel rounded-xl px-3 py-2 sm:px-4 sm:py-2.5 shrink-0">
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

          <span className="hidden sm:inline text-white/20" aria-hidden>
            |
          </span>

          <div className="min-w-0 flex-1 basis-[8rem]">
            <p className="text-sm font-medium truncate" title={tabTitle}>
              {tabTitle}
            </p>
            {slotHint ? (
              <p className="text-[11px] text-muted-foreground truncate hidden md:block" title={slotHint}>
                {slotHint}
              </p>
            ) : null}
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
              disabled={loading || !data}
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
      </div>

      {error && <p className="text-sm text-rose-300 shrink-0">{error}</p>}

      {data?.today_chapter?.done && tab === "morning" && (
        <div className="rounded-lg border border-teal-500/30 bg-teal-500/10 px-3 py-2 text-xs sm:text-sm text-teal-100 shrink-0">
          Morning done (+10).{" "}
          <a href="/productivity?tab=plan" className="underline">
            Confirm plan
          </a>{" "}
          (+10)
        </div>
      )}

      <div className="min-h-0 flex-1 overflow-y-auto rounded-xl border border-white/10 bg-black/40 px-4 sm:px-6 py-4 sm:py-5 space-y-5">
          {loading && !data ? (
            <p className="text-base text-muted-foreground">Loading devotion…</p>
          ) : tab === "morning" && data ? (
            <>
              <p className="text-sm text-muted-foreground md:hidden">{data.morning.note}</p>
              <VerseList chapter={data.morning_chapter} />
              <PrayerBlock title="The Lord's Prayer" body={data.morning.lords_prayer || ""} />
              <NotesField
                slot="morning"
                value={data.morning.notes || ""}
                onSaved={() => void load()}
              />
            </>
          ) : tab === "afternoon" && data ? (
            <>
              <p className="text-sm text-muted-foreground md:hidden">{data.afternoon.note}</p>
              <VerseList chapter={data.afternoon_chapter} />
              <PrayerBlock
                title="Prayer — wisdom, health, healing, work"
                body={data.afternoon.prayer || ""}
              />
              <NotesField
                slot="afternoon"
                value={data.afternoon.notes || ""}
                onSaved={() => void load()}
              />
            </>
          ) : tab === "evening" && data ? (
            <>
              <p className="text-sm text-muted-foreground md:hidden">{data.evening.note}</p>
              <VerseList chapter={data.evening_chapter} />
              <PrayerBlock
                title={`Worship — ${data.evening.worship_title || "Praise"}`}
                body={`${data.evening.worship_opening || ""}\n\nTheme: ${data.evening.worship_theme || "praise"}`}
              />
              <NotesField
                slot="evening"
                value={data.evening.notes || ""}
                onSaved={() => void load()}
              />
            </>
          ) : null}
      </div>
    </div>
  );
}
