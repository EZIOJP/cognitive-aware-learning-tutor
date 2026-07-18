import { format } from "date-fns";
import { useLayoutEffect, useRef, useState } from "react";
import { Copy, Check } from "lucide-react";
import {
  fmtDurationMinutes,
  scoreAccent,
  scoreLabel,
  shortAppName,
  type MergedInterval,
} from "./planVsActualUtils";

export type EventAnchorRect = {
  top: number;
  left: number;
  width: number;
  height: number;
};

export type ActivityDetailPanelProps = {
  title: string;
  start: Date;
  end: Date;
  items?: MergedInterval[];
  totalSeconds?: number;
  onClose: () => void;
  popup?: boolean;
  anchor?: EventAnchorRect | null;
  containerWidth?: number;
  containerHeight?: number;
  cycleIndex?: number;
  cycleTotal?: number;
  cycleLabel?: "overlapped" | "in hour";
  onCyclePrev?: () => void;
  onCycleNext?: () => void;
  plannedBlock?: { title: string; category: string; minutes: number };
  planContext?: "on_plan" | "focus" | "distraction" | "drift";
};

const CARD_W = 320;
const CARD_MAX_H = 380;
const SHELL =
  "rounded-xl border border-sky-400/45 bg-gradient-to-b from-slate-900 via-sky-950/98 to-slate-950 p-3.5 space-y-2.5 shadow-[0_6px_0_rgba(15,23,42,0.88),0_16px_32px_rgba(0,0,0,0.45),inset_0_1px_0_rgba(147,197,253,0.35)]";

function formatTimeRange(start: Date, end: Date): string {
  const sameDay = start.toDateString() === end.toDateString();
  const day = format(start, "EEE, MMM d");
  const t0 = format(start, "h:mm a");
  const t1 = format(end, "h:mm a");
  return sameDay ? `${day} · ${t0} – ${t1}` : `${format(start, "MMM d h:mm a")} – ${format(end, "MMM d h:mm a")}`;
}

function placeNearAnchor(anchor: EventAnchorRect, cw: number, ch: number): { top: number; left: number } {
  const gap = 10;
  let left = anchor.left + anchor.width + gap;
  let top = anchor.top + anchor.height / 2 - CARD_MAX_H / 2;
  if (left + CARD_W > cw - 8) left = anchor.left - CARD_W - gap;
  if (left < 8) left = Math.min(cw - CARD_W - 8, anchor.left + anchor.width / 2 - CARD_W / 2);
  top = Math.max(8, Math.min(ch - CARD_MAX_H - 8, top));
  return { top, left };
}

function TitleRow({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const [expanded, setExpanded] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* ignore */
    }
  };

  return (
    <div className="mt-1.5 space-y-1">
      <div className="flex items-start justify-between gap-2">
        <p
          className={`text-[11px] text-sky-100/90 leading-snug flex-1 ${expanded ? "" : "line-clamp-3"}`}
          title={text}
        >
          {text}
        </p>
        <div className="flex shrink-0 gap-1">
          {text.length > 80 && (
            <button
              type="button"
              onClick={() => setExpanded((v) => !v)}
              className="text-[10px] px-1.5 py-0.5 rounded border border-white/10 text-sky-200/70 hover:bg-white/5"
            >
              {expanded ? "Less" : "More"}
            </button>
          )}
          <button
            type="button"
            onClick={() => void copy()}
            className="text-[10px] p-1 rounded border border-white/10 text-sky-200/70 hover:bg-white/5"
            title="Copy title"
          >
            {copied ? <Check size={12} /> : <Copy size={12} />}
          </button>
        </div>
      </div>
    </div>
  );
}

function PageBreakdown({ item }: { item: MergedInterval }) {
  const pages = (item.children ?? []).filter((child) => child.window_title || child.site);
  if (pages.length <= 1) return null;

  return (
    <details className="rounded-lg border border-white/10 bg-white/[0.03] px-2 py-1">
      <summary className="cursor-pointer text-[10px] text-sky-200/80 hover:text-sky-100">
        Show {pages.length} pages / sessions
      </summary>
      <ul className="mt-1.5 max-h-32 overflow-y-auto space-y-1 pr-1">
        {pages.map((page, idx) => (
          <li key={`${page.start_time}-${idx}`} className="text-[10px] text-sky-100/80 leading-snug border-t border-white/5 pt-1">
            <div className="flex justify-between gap-2 tabular-nums text-sky-300/55">
              <span>
                {format(new Date(page.start_time), "h:mm a")} – {format(new Date(page.end_time), "h:mm a")}
              </span>
              <span>{fmtDurationMinutes(Math.round(page.duration_seconds / 60))}</span>
            </div>
            <div className="line-clamp-2" title={page.window_title || page.site || ""}>
              {page.window_title || page.site}
            </div>
          </li>
        ))}
      </ul>
    </details>
  );
}

function ActivityRow({
  item,
}: {
  item: MergedInterval;
}) {
  const name = shortAppName(item.app_name || item.category);
  const exe = item.app_name && shortAppName(item.app_name) !== name ? item.app_name : null;
  const mins = Math.round(item.duration_seconds / 60);
  const titleSnippet = item.window_title?.trim();
  const score = item.productivity_score ?? 35;

  return (
    <li className="rounded-lg border border-white/10 bg-black/30 px-3 py-2.5 space-y-1.5">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <span className={`w-2 h-2 rounded-full shrink-0 ${scoreAccent(score)}`} />
          <div className="min-w-0">
            <span className="text-sm font-semibold text-sky-50 truncate block">{name}</span>
            {exe && <span className="text-[10px] text-sky-300/50 truncate block">{exe}</span>}
          </div>
        </div>
        <span className="text-xs tabular-nums text-sky-200 shrink-0">{fmtDurationMinutes(mins)}</span>
      </div>
      <div className="flex flex-wrap gap-1.5 text-[10px]">
        {item.category && (
          <span className="px-2 py-0.5 rounded-full bg-sky-500/15 text-sky-200 border border-sky-400/20">
            {item.category}
          </span>
        )}
        <span className="px-2 py-0.5 rounded-full bg-white/5 text-sky-100/80 border border-white/10">
          {score} · {scoreLabel(score)}
        </span>
        {item.site && (
          <span className="px-2 py-0.5 rounded-full bg-cyan-500/10 text-cyan-200/90 border border-cyan-400/20 truncate max-w-[140px]">
            {item.site}
          </span>
        )}
      </div>
      <p className="text-[10px] text-sky-300/50 tabular-nums">
        {format(new Date(item.start_time), "h:mm a")} – {format(new Date(item.end_time), "h:mm a")}
        {item.merged_count > 1 && (
          <span className="ml-1 text-amber-200/70">
            · merges {item.merged_count} tracker sessions (display only)
          </span>
        )}
      </p>
      <PageBreakdown item={item} />
      {titleSnippet && <TitleRow text={titleSnippet} />}
    </li>
  );
}

export function ActivityDetailCardBody({
  title,
  start,
  end,
  items = [],
  totalSeconds = 0,
  plannedBlock,
  planContext,
  onClose,
  cycleIndex,
  cycleTotal,
  cycleLabel = "overlapped",
  onCyclePrev,
  onCycleNext,
}: ActivityDetailPanelProps) {
  const sorted = [...items].sort((a, b) => b.duration_seconds - a.duration_seconds);
  const totalMins = Math.round(totalSeconds / 60);
  const canCycle = (cycleTotal ?? 1) >= 2;
  const totalSessions = sorted.reduce((n, item) => n + (item.merged_count ?? 1), 0);
  const uniqueApps = new Set(sorted.map((item) => item.app_name).filter(Boolean)).size;
  const showAggregateBanner = sorted.length > 1 || totalSessions > sorted.length;

  const planLabel =
    planContext === "focus" || planContext === "on_plan"
      ? "During planned block · productive"
      : planContext === "distraction"
        ? "Distraction during plan"
        : planContext === "drift"
          ? "Outside planned blocks"
          : null;
  const planClass =
    planContext === "focus" || planContext === "on_plan"
      ? "bg-emerald-500/15 text-emerald-200 border-emerald-500/30"
      : planContext === "distraction"
        ? "bg-rose-500/15 text-rose-200 border-rose-500/30"
        : "bg-amber-500/15 text-amber-200 border-amber-500/30";

  return (
    <>
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <p className="text-[10px] uppercase tracking-wider text-sky-300/70 font-medium">
            {plannedBlock ? "Planned block" : "Tracked activity"}
          </p>
          <h3 className="text-base font-semibold text-sky-50 truncate">{plannedBlock?.title ?? title}</h3>
          <p className="text-xs text-sky-200/80 mt-0.5 tabular-nums">{formatTimeRange(start, end)}</p>
          {planLabel && !plannedBlock && (
            <span className={`inline-block mt-1 text-[10px] px-2 py-0.5 rounded-full border ${planClass}`}>
              {planLabel}
            </span>
          )}
        </div>
        <button
          type="button"
          onClick={onClose}
          className="shrink-0 text-xs px-2 py-1 rounded border border-white/10 text-muted-foreground hover:text-foreground hover:bg-white/5"
        >
          Close
        </button>
      </div>

      {canCycle && (
        <div className="flex items-center justify-between gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 px-2 py-2">
          <button type="button" onClick={onCyclePrev} className="text-xs px-2.5 py-1 rounded-md border border-white/15 hover:bg-white/10 text-amber-50" aria-label="Previous">
            ←
          </button>
          <span className="text-[11px] text-amber-100/95 text-center min-w-[5.5rem]">
            {cycleLabel === "in hour" ? "More in this hour" : "More overlapped"}
          </span>
          <button type="button" onClick={onCycleNext} className="text-xs px-2.5 py-1 rounded-md border border-white/15 hover:bg-white/10 text-amber-50" aria-label="Next">
            →
          </button>
        </div>
      )}

      {plannedBlock ? (
        <div className="rounded-lg border border-violet-500/25 bg-violet-500/10 px-3 py-3 space-y-1">
          <p className="text-sm text-violet-100">{plannedBlock.category}</p>
          <p className="text-xs text-violet-200/70">{plannedBlock.minutes}m planned</p>
        </div>
      ) : (
        <>
          {showAggregateBanner && (
            <p className="text-[10px] text-amber-200/80 leading-snug rounded-lg border border-amber-500/25 bg-amber-500/10 px-2.5 py-2">
              <strong className="text-amber-100">Aggregated view:</strong> combines {totalSessions} tracker
              session{totalSessions === 1 ? "" : "s"} across {uniqueApps} app{uniqueApps === 1 ? "" : "s"} — gaps
              merged for readability (raw data unchanged).
            </p>
          )}
          <div className="flex flex-wrap gap-2 text-[11px]">
            <span className="px-2 py-0.5 rounded-full bg-sky-500/15 text-sky-200 border border-sky-400/20">
              {sorted.length} block{sorted.length === 1 ? "" : "s"}
            </span>
            <span className="px-2 py-0.5 rounded-full bg-white/5 text-sky-100/90 border border-white/10">
              {fmtDurationMinutes(totalMins)} total
            </span>
          </div>
          <ul className="space-y-2 overflow-y-auto pr-1 max-h-56">
            {sorted.map((item) => (
              <ActivityRow
                key={`${item.start_time}-${item.app_name}`}
                item={item}
              />
            ))}
          </ul>
        </>
      )}
    </>
  );
}

export function ActivityDetailPanel(props: ActivityDetailPanelProps) {
  const cardRef = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState({ top: 12, left: 12 });
  const cw = props.containerWidth ?? 400;
  const ch = props.containerHeight ?? 400;

  useLayoutEffect(() => {
    if (!props.popup || !props.anchor) return;
    const h = cardRef.current?.offsetHeight ?? CARD_MAX_H;
    const placed = placeNearAnchor(props.anchor, cw, ch);
    if (placed.top + h > ch - 8) placed.top = Math.max(8, ch - h - 8);
    setPos(placed);
  }, [props.popup, props.anchor, props.cycleIndex, props.title, cw, ch]);

  if (props.popup) {
    return (
      <div
        ref={cardRef}
        role="dialog"
        aria-modal="true"
        aria-label="Activity detail"
        className={`absolute z-[60] w-[320px] max-w-[calc(100%-16px)] animate-in zoom-in-95 fade-in duration-150 ${SHELL}`}
        style={{ top: pos.top, left: pos.left }}
        onClick={(e) => e.stopPropagation()}
      >
        <ActivityDetailCardBody {...props} />
      </div>
    );
  }

  return (
    <div className={`max-w-md w-full animate-in fade-in slide-in-from-top-1 duration-200 ${SHELL}`}>
      <ActivityDetailCardBody {...props} />
    </div>
  );
}
