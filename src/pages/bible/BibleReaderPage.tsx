import { useCallback, useEffect, useState } from "react";
import { Check } from "lucide-react";
import {
  bibleChapterHeartbeat,
  chapterKey,
  fetchBibleToday,
  tickBibleChapter,
  type BibleChapter,
  type BibleState,
  type TodayChapter,
} from "../../api/bibleClient";
import { formatHoursMinsPair } from "../../utils/formatDuration";

export function BibleReaderPage() {
  const [payload, setPayload] = useState<BibleChapter | null>(null);
  const [today, setToday] = useState<TodayChapter | null>(null);
  const [state, setState] = useState<BibleState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const goal = state?.chapter_goal;
  const chapterDone = Boolean(today?.done || goal?.met);
  const gate = state?.gate as
    | {
        day_unlimited?: boolean;
        productive_minutes?: number;
        daily_goal_minutes?: number;
        unlock_mode?: string;
      }
    | undefined;

  const loadToday = useCallback(async () => {
    const data = await fetchBibleToday("web");
    setState(data);
    setToday(data.today_chapter);
    setPayload(data.chapter);
    return data;
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    (async () => {
      try {
        await loadToday();
        if (!cancelled) setError(null);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [loadToday]);

  useEffect(() => {
    if (!today?.book || !today?.chapter) return;
    const book = today.book;
    const chapter = today.chapter;
    const tick = () => {
      void bibleChapterHeartbeat(book, chapter, document.visibilityState === "visible", 1)
        .then((s) => {
          setState(s);
          if (s.today_chapter) setToday(s.today_chapter);
        })
        .catch(() => undefined);
    };
    tick();
    const id = window.setInterval(tick, 20_000);
    const onVis = () => {
      if (document.visibilityState === "visible") tick();
    };
    document.addEventListener("visibilitychange", onVis);
    return () => {
      window.clearInterval(id);
      document.removeEventListener("visibilitychange", onVis);
    };
  }, [today?.book, today?.chapter]);

  const onTick = async () => {
    if (!today) return;
    try {
      const s = await tickBibleChapter(today.book, today.chapter, !chapterDone);
      setState(s);
      if (s.today_chapter) setToday(s.today_chapter);
      else {
        setToday({
          ...today,
          done: Boolean(s.done ?? !chapterDone),
        });
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const title = today?.label || (payload ? `${payload.name} ${payload.chapter}` : "Today’s chapter");

  return (
    <div className="flex h-[calc(100vh-4rem)] flex-col gap-4 p-6">
      <header className="flex flex-wrap items-end justify-between gap-3 gloss-panel rounded-xl px-5 py-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Bible</h1>
          <p className="text-sm text-muted-foreground mt-1">
            One chapter today — mark it done (+10), then confirm today’s plan on Productivity (+10)
          </p>
        </div>
        <div className="flex flex-wrap gap-3 text-sm tabular-nums">
          <span className="rounded-md bg-black/30 px-3 py-1.5">
            Chapter goal:{" "}
            <strong>
              {goal?.done ?? 0}/{goal?.target ?? 1}
            </strong>
            {goal?.met ? " ✓" : ""}
          </span>
          <span className="rounded-md bg-black/30 px-3 py-1.5">
            Study:{" "}
            <strong>
              {formatHoursMinsPair(gate?.productive_minutes, gate?.daily_goal_minutes)}
            </strong>
          </span>
          <span className="rounded-md bg-black/30 px-3 py-1.5">
            Unlock: <strong>{gate?.unlock_mode || (gate?.day_unlimited ? "unlimited" : "—")}</strong>
          </span>
        </div>
      </header>

      {chapterDone && (
        <div className="rounded-xl border border-teal-500/30 bg-teal-500/10 px-5 py-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-base text-teal-100 font-medium">Done for today — {title}</p>
            <p className="text-sm text-teal-100/80 mt-1">
              Bible +10 earned. Stay and re-read / meditate — full text stays below. Next unlock step:
              confirm plan/goals on Productivity (+10).
            </p>
          </div>
          <a
            href="/productivity?tab=plan"
            className="text-sm px-4 py-2 rounded-md bg-teal-500/25 text-teal-50 border border-teal-400/40 hover:bg-teal-500/35"
          >
            Go to Plan
          </a>
        </div>
      )}

      {error && <p className="text-sm text-rose-300">{error}</p>}

      <div className="flex min-h-0 flex-1 flex-col gap-3">
        <div className="flex flex-wrap items-center justify-between gap-2 gloss-panel rounded-xl px-4 py-3">
          <div className="text-base font-medium">{title}</div>
          <button
            type="button"
            onClick={() => void onTick()}
            disabled={!today}
            className={`inline-flex items-center gap-1.5 rounded-md px-4 py-2 text-sm font-medium ${
              chapterDone
                ? "bg-emerald-500/20 text-emerald-100 border border-emerald-400/40"
                : "bg-primary/90 text-primary-foreground"
            }`}
          >
            <Check className="h-4 w-4" />
            {chapterDone ? "Chapter done today" : "Mark chapter done"}
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto rounded-xl border border-white/10 bg-black/40 px-6 py-5">
          {loading && !payload ? (
            <p className="text-base text-muted-foreground">Loading today’s chapter…</p>
          ) : (
            <ol className="space-y-5 text-lg leading-relaxed">
              {(payload?.verses || []).map((v) => (
                <li key={v.number} className="flex gap-4">
                  <span className="w-10 shrink-0 text-right text-sm text-muted-foreground tabular-nums pt-1">
                    {v.number}
                  </span>
                  <span className="text-foreground/95">{v.text}</span>
                </li>
              ))}
            </ol>
          )}
        </div>

        <p className="text-xs text-muted-foreground px-1">
          {payload?.version_name || "World English Bible"} · public domain · one chapter per day · mark
          done only when you choose ·{" "}
          <button
            type="button"
            className="underline opacity-70 hover:opacity-100"
            onClick={() => void loadToday().catch((e) => setError(e instanceof Error ? e.message : String(e)))}
          >
            refresh
          </button>
          {today?.key ? (
            <span className="opacity-50"> · {chapterKey(today.book, today.chapter)}</span>
          ) : null}
          {chapterDone ? (
            <span className="opacity-60">
              {" "}
              · click “Chapter done today” to untick if you marked early (or clear{" "}
              <code className="text-[10px]">chapters_completed</code> in today’s{" "}
              <code className="text-[10px]">data/bible/day_*.json</code>)
            </span>
          ) : null}
        </p>
      </div>
    </div>
  );
}
