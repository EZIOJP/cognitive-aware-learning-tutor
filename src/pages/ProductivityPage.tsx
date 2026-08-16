import { useState, useEffect, useCallback, useMemo, useRef, type ReactNode } from "react";
import {
  Monitor, Globe, RefreshCw, AlertCircle, CheckCircle2,
  Clock, Zap, Terminal, Code2, BookOpen, PenLine,
  Gamepad2, Music, MessageSquare, FileText, Folder, Cpu, CalendarDays,
  ChevronDown, ChevronRight, Download, Loader2,
} from "lucide-react";
import { Views, type View } from "react-big-calendar";
import { fetchDesktopStats, fetchBrowserStats, fetchTrackerHealth, fetchDesktopTimeline, forceTrackerSync, clearDemoClock, fetchDemoClock } from "../api/behaviorClient";
import type { DesktopStats, BrowserStats, AppSession, BrowserSite, BrowserDomain, TrackerHealth, DesktopTimeline, DemoClockStatus } from "../api/behaviorClient";
import { PlannerCalendar } from "../components/productivity/PlannerCalendar";
import { GlanceBar } from "../components/productivity/GlanceBar";
import { PlanVsActualDashboard } from "../components/productivity/PlanVsActualDashboard";
import { TimetablePanel } from "../components/productivity/TimetablePanel";
import { PlanningSettingsPanel } from "../components/productivity/PlanningSettingsPanel";
import { DemoModePanel } from "../components/productivity/DemoModePanel";
import { RoutinesPanel } from "../components/productivity/RoutinesPanel";
import { ProposeStepPanel, applyRangeForHorizon } from "../components/productivity/ProposeStepPanel";
import { resolveProposedOverlaps } from "../components/productivity/resolveProposedOverlaps";
import { proposeBlockStatKind, blockDurationMinutes } from "../components/productivity/proposeBlockStats";
import { Link, useSearchParams } from "react-router";
import { useEaster, useLongPress } from "../easter";
import {
  fetchAdherence,
  createPlannerBlock,
  downloadProductivityWeekExport,
  proposeWeekFromExport,
  applyProposedBlocks,
  fetchPlannerBlocks,
  fetchRoutines,
  syncPlannerToGoogleCalendar,
  type AdherenceSummary,
  type ProposedPlannerBlock,
  type PlannerRoutine,
} from "../api/plannerClient";
import { fetchDueReview } from "../api/globalQuizClient";
import { fetchHubDaily } from "../api/hubClient";
import ClassificationReview from "../components/productivity/ClassificationReview";
import ProductivityPolicyPanel from "../components/productivity/ProductivityPolicyPanel";
import ProductivityGoalsPanel, {
  formatGoalsForPrompt,
  loadProductivityGoals,
} from "../components/productivity/ProductivityGoalsPanel";
import SessionOverridePanel from "../components/productivity/SessionOverridePanel";
import WearablesSyncPanel from "../components/productivity/WearablesSyncPanel";
import GoogleCalendarSyncPanel from "../components/productivity/GoogleCalendarSyncPanel";
import PlannerRemindersPanel from "../components/productivity/PlannerRemindersPanel";
import {
  statsRangeForView,
  draftCoveredBySavedBlocks,
  type CalendarStatsView,
} from "../components/productivity/planVsActualUtils";
import { endOfDay, startOfDay } from "date-fns";

// ── Helpers ──────────────────────────────────────────────────────────────────

function fmtSeconds(s: number): string {
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  const rem = m % 60;
  return rem > 0 ? `${h}h ${rem}m` : `${h}h`;
}

function scoreColor(score: number): string {
  if (score >= 80) return "text-emerald-400";
  if (score >= 60) return "text-green-400";
  if (score >= 40) return "text-yellow-400";
  if (score >= 20) return "text-orange-400";
  return "text-red-400";
}

function scoreBg(score: number): string {
  if (score >= 80) return "bg-emerald-500";
  if (score >= 60) return "bg-green-500";
  if (score >= 40) return "bg-yellow-500";
  if (score >= 20) return "bg-orange-500";
  return "bg-red-500";
}

function categoryIcon(category: string) {
  const c = category.toLowerCase();
  if (c.includes("ide") || c.includes("code") || c.includes("editor")) return <Code2 size={14} />;
  if (c.includes("terminal")) return <Terminal size={14} />;
  if (c.includes("study") || c.includes("reading") || c.includes("coursework")) return <BookOpen size={14} />;
  if (c.includes("browser") || c.includes("web")) return <Globe size={14} />;
  if (c.includes("communication") || c.includes("chat")) return <MessageSquare size={14} />;
  if (c.includes("music") || c.includes("media")) return <Music size={14} />;
  if (c.includes("gaming") || c.includes("game")) return <Gamepad2 size={14} />;
  if (c.includes("office") || c.includes("doc")) return <FileText size={14} />;
  if (c.includes("file") || c.includes("manager")) return <Folder size={14} />;
  if (c.includes("system") || c.includes("tool") || c.includes("dev")) return <Cpu size={14} />;
  return <Monitor size={14} />;
}

function toApiDay(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

const ROUTINE_WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"] as const;

/** Local wall-clock materialization of enabled routines (fallback if API omit them). */
function materializeRoutineBlocks(
  routines: PlannerRoutine[],
  rangeStart: string,
  horizonDays: number,
): ProposedPlannerBlock[] {
  const out: ProposedPlannerBlock[] = [];
  const base = new Date(`${rangeStart}T12:00:00`);
  for (let i = 0; i < Math.max(1, horizonDays); i++) {
    const day = new Date(base);
    day.setDate(base.getDate() + i);
    const key = ROUTINE_WEEKDAYS[(day.getDay() + 6) % 7];
    for (const r of routines) {
      if (!r.enabled) continue;
      const days = r.days?.length ? r.days : [...ROUTINE_WEEKDAYS];
      if (!days.includes(key)) continue;
      const [sh, sm] = (r.start_time || "09:00").split(":").map((x) => Number(x) || 0);
      let eh: number;
      let em: number;
      if (r.end_time) {
        [eh, em] = r.end_time.split(":").map((x) => Number(x) || 0);
      } else {
        const total = sh * 60 + sm + Math.max(1, r.duration_minutes || 30);
        eh = Math.floor(total / 60) % 24;
        em = total % 60;
      }
      const start = new Date(day.getFullYear(), day.getMonth(), day.getDate(), sh, sm, 0, 0);
      let end = new Date(day.getFullYear(), day.getMonth(), day.getDate(), eh, em, 0, 0);
      if (end <= start) end = new Date(start.getTime() + 30 * 60_000);
      out.push({
        title: r.title,
        category: r.category || "personal",
        start_at: start.toISOString(),
        end_at: end.toISOString(),
        source: "routine",
      });
    }
  }
  return out;
}

function blocksOverlap(a: ProposedPlannerBlock, b: ProposedPlannerBlock): boolean {
  const as = new Date(a.start_at).getTime();
  const ae = new Date(a.end_at).getTime();
  const bs = new Date(b.start_at).getTime();
  const be = new Date(b.end_at).getTime();
  return as < be && bs < ae;
}

function calendarViewToStats(view: View): CalendarStatsView {
  if (view === Views.DAY || view === "day") return "day";
  if (view === Views.MONTH || view === "month") return "month";
  return "week";
}

function eachApiDay(from: Date, to: Date): string[] {
  const out: string[] = [];
  const cursor = new Date(from);
  cursor.setHours(0, 0, 0, 0);
  const end = new Date(to);
  end.setHours(0, 0, 0, 0);
  while (cursor.getTime() <= end.getTime()) {
    out.push(toApiDay(cursor));
    cursor.setDate(cursor.getDate() + 1);
  }
  return out;
}

async function fetchDesktopStatsForRange(from: Date, to: Date): Promise<DesktopStats> {
  const days = eachApiDay(from, to);
  if (days.length === 1) return fetchDesktopStats(days[0]);
  const results = await Promise.allSettled(days.map((d) => fetchDesktopStats(d)));
  const byKey = new Map<string, AppSession>();
  let total = 0;
  let weighted = 0;
  let tracker_running = false;
  let last_event_at: string | null = null;
  for (const r of results) {
    if (r.status !== "fulfilled") continue;
    const row = r.value;
    tracker_running = tracker_running || row.tracker_running;
    if (row.last_event_at && (!last_event_at || row.last_event_at > last_event_at)) {
      last_event_at = row.last_event_at;
    }
    total += row.total_seconds;
    weighted += row.avg_productivity_score * row.total_seconds;
    for (const sess of row.sessions) {
      const key = `${sess.kind ?? "app"}:${sess.exe}`;
      const prev = byKey.get(key);
      if (!prev) {
        byKey.set(key, {
          ...sess,
          sites: sess.sites?.map((s) => ({ ...s })),
        });
        continue;
      }
      prev.seconds += sess.seconds;
      if (sess.sites?.length) {
        const siteMap = new Map((prev.sites ?? []).map((s) => [s.site, s]));
        for (const site of sess.sites) {
          const existing = siteMap.get(site.site);
          if (existing) existing.seconds += site.seconds;
          else siteMap.set(site.site, { ...site });
        }
        prev.sites = [...siteMap.values()].sort((a, b) => b.seconds - a.seconds);
      }
    }
  }
  return {
    sessions: [...byKey.values()].sort((a, b) => b.seconds - a.seconds),
    total_seconds: total,
    avg_productivity_score: total > 0 ? Math.round(weighted / total) : 0,
    source: "range",
    date: `${days[0] ?? ""}…${days[days.length - 1] ?? ""}`,
    tracker_running,
    last_event_at,
  };
}

async function fetchBrowserStatsForRange(from: Date, to: Date): Promise<BrowserStats> {
  const days = eachApiDay(from, to);
  if (days.length === 1) return fetchBrowserStats(days[0]);
  const results = await Promise.allSettled(days.map((d) => fetchBrowserStats(d)));
  const domainMap = new Map<string, BrowserDomain>();
  const category_breakdown: Record<string, number> = {};
  let events_today = 0;
  let total_events = 0;
  let weighted = 0;
  let weightSec = 0;
  let connected = false;
  let source: string | null = null;
  const recent_sites: string[] = [];
  for (const r of results) {
    if (r.status !== "fulfilled") continue;
    const row = r.value;
    connected = connected || row.connected;
    source = row.source ?? source;
    events_today += row.events_today;
    total_events += row.total_events;
    for (const [cat, sec] of Object.entries(row.category_breakdown ?? {})) {
      category_breakdown[cat] = (category_breakdown[cat] ?? 0) + sec;
      weighted += (row.avg_productivity_score || 0) * sec;
      weightSec += sec;
    }
    for (const d of row.top_domains ?? []) {
      const prev = domainMap.get(d.domain);
      if (prev) prev.seconds += d.seconds;
      else domainMap.set(d.domain, { ...d });
    }
    for (const s of row.recent_sites ?? []) {
      if (!recent_sites.includes(s)) recent_sites.push(s);
    }
  }
  const top_domains = [...domainMap.values()].sort((a, b) => b.seconds - a.seconds).slice(0, 12);
  return {
    connected,
    events_today,
    total_events,
    top_category: Object.entries(category_breakdown).sort((a, b) => b[1] - a[1])[0]?.[0] ?? "—",
    avg_productivity_score: weightSec > 0 ? Math.round(weighted / weightSec) : 0,
    top_domains,
    recent_sites: recent_sites.slice(0, 20),
    category_breakdown,
    date: `${days[0] ?? ""}…${days[days.length - 1] ?? ""}`,
    source,
  };
}

// ── App bar row ───────────────────────────────────────────────────────────────

function AppRow({
  session,
  maxSeconds,
  leading,
}: {
  session: AppSession;
  maxSeconds: number;
  /** Fixed-width leading control (e.g. expand chevron) so bars stay aligned */
  leading?: ReactNode;
}) {
  const pct = maxSeconds > 0 ? (session.seconds / maxSeconds) * 100 : 0;
  return (
    <div className="flex items-center gap-3 py-2">
      <div className="w-3.5 shrink-0 flex items-center justify-center">
        {leading ?? null}
      </div>
      <div className="flex items-center gap-2 w-36 min-w-0">
        <span className="text-muted-foreground">{categoryIcon(session.category)}</span>
        <span className="text-sm font-medium truncate" title={session.exe}>{session.exe}</span>
      </div>
      <div className="flex-1 relative h-5 rounded-full bg-white/5 overflow-hidden">
        <div
          className={`h-full rounded-full ${scoreBg(session.productivity_score)} opacity-80 transition-all duration-500`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs text-muted-foreground w-14 text-right tabular-nums">{fmtSeconds(session.seconds)}</span>
      <span className={`text-xs font-semibold w-8 text-right tabular-nums ${scoreColor(session.productivity_score)}`}>
        {session.productivity_score}
      </span>
    </div>
  );
}

function SiteRow({ site, maxSeconds }: { site: BrowserSite; maxSeconds: number }) {
  const pct = maxSeconds > 0 ? (site.seconds / maxSeconds) * 100 : 0;
  return (
    <div className="flex items-center gap-3 py-1.5">
      <div className="w-3.5 shrink-0" />
      <div className="flex items-center gap-2 w-44 min-w-0">
        <Globe size={12} className="text-sky-400 shrink-0" />
        <div className="min-w-0">
          <span className="text-xs truncate text-foreground/80 block" title={site.site}>{site.site}</span>
          {site.category && (
            <span className="text-[10px] truncate text-muted-foreground/75 block" title={site.category}>
              {site.category}
            </span>
          )}
        </div>
      </div>
      <div className="flex-1 relative h-4 rounded-full bg-white/5 overflow-hidden">
        <div
          className={`h-full rounded-full ${scoreBg(site.productivity_score)} opacity-70`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-[11px] text-muted-foreground w-14 text-right tabular-nums">{fmtSeconds(site.seconds)}</span>
      <span className={`text-[11px] font-semibold w-8 text-right tabular-nums ${scoreColor(site.productivity_score)}`}>
        {site.productivity_score}
      </span>
    </div>
  );
}

function BrowserGroupRow({ session, maxSeconds }: { session: AppSession; maxSeconds: number }) {
  const [open, setOpen] = useState(true);
  const sites = session.sites ?? [];
  const siteMax = sites[0]?.seconds ?? session.seconds;

  return (
    <div className="py-1">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full text-left"
      >
        <AppRow
          session={session}
          maxSeconds={maxSeconds}
          leading={
            open ? (
              <ChevronDown size={14} className="text-muted-foreground" />
            ) : (
              <ChevronRight size={14} className="text-muted-foreground" />
            )
          }
        />
      </button>
      {open && sites.length > 0 && (
        <div className="border-l border-white/10 ml-5 mb-1">
          {sites.map((site) => (
            <SiteRow key={site.site} site={site} maxSeconds={siteMax} />
          ))}
        </div>
      )}
    </div>
  );
}

// ── Day timeline strip ────────────────────────────────────────────────────────

function timelineColor(category: string | null): string {
  const c = (category || "").toLowerCase();
  if (c.includes("ide") || c.includes("code") || c.includes("terminal")) return "bg-emerald-500";
  if (c.includes("study") || c.includes("coursework") || c.includes("reading")) return "bg-blue-500";
  if (c.includes("browser")) return "bg-sky-500";
  if (c.includes("communication")) return "bg-orange-500";
  if (c.includes("gaming") || c.includes("video")) return "bg-red-500";
  return "bg-violet-500";
}

function DayTimeline({ timeline, listTotalSeconds }: { timeline: DesktopTimeline | null; listTotalSeconds?: number }) {
  if (!timeline?.intervals.length) return null;

  const dayStart = new Date(timeline.date);
  dayStart.setHours(0, 0, 0, 0);
  const dayMs = 24 * 60 * 60 * 1000;

  return (
    <div className="space-y-2">
      <div className="flex justify-between text-[10px] text-muted-foreground tabular-nums">
        <span>12am</span>
        <span>6am</span>
        <span>12pm</span>
        <span>6pm</span>
        <span>12am</span>
      </div>
      <div className="relative h-8 rounded-lg bg-white/5 overflow-hidden flex">
        {timeline.intervals.map((iv) => {
          const start = new Date(iv.start_time).getTime() - dayStart.getTime();
          const left = Math.max(0, (start / dayMs) * 100);
          const width = Math.max(0.15, (iv.duration_seconds / 86400) * 100);
          return (
            <div
              key={iv.session_id}
              className={`absolute top-0 bottom-0 ${timelineColor(iv.category)} opacity-80`}
              style={{ left: `${left}%`, width: `${width}%` }}
              title={`${iv.site || iv.category || "Activity"} · ${fmtSeconds(iv.duration_seconds)}${iv.window_title ? ` · ${iv.window_title}` : ""}`}
            />
          );
        })}
      </div>
      <p className="text-xs text-muted-foreground">
        {timeline.intervals.length} activity blocks · {fmtSeconds(timeline.total_seconds)} tracked
        {listTotalSeconds != null && Math.abs(timeline.total_seconds - listTotalSeconds) > 60 && (
          <span className="text-amber-400/80"> · list total {fmtSeconds(listTotalSeconds)}</span>
        )}
      </p>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export function ProductivityPage() {
  const { burst } = useEaster();
  const trackerEgg = useLongPress(600, () => burst("cat"));
  const [desktop, setDesktop] = useState<DesktopStats | null>(null);
  const [browser, setBrowser] = useState<BrowserStats | null>(null);
  const [trackerHealth, setTrackerHealth] = useState<TrackerHealth | null>(null);
  const [timeline, setTimeline] = useState<DesktopTimeline | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [loadErrors, setLoadErrors] = useState<string[]>([]);
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date());
  const [adherence, setAdherence] = useState<AdherenceSummary | null>(null);
  const [dueReviews, setDueReviews] = useState(0);
  const [sleepHours, setSleepHours] = useState<number | null>(null);
  const [plannerDay, setPlannerDay] = useState(() => {
    const raw = new URLSearchParams(window.location.search).get("day");
    if (raw && /^\d{4}-\d{2}-\d{2}$/.test(raw)) {
      const [y, m, d] = raw.split("-").map(Number);
      return new Date(y, m - 1, d, 12, 0, 0, 0);
    }
    return new Date();
  });
  const [calendarView, setCalendarView] = useState<View>(Views.DAY);
  const [searchParams, setSearchParams] = useSearchParams();
  const [demoClock, setDemoClock] = useState<DemoClockStatus | null>(null);
  const rawTab = searchParams.get("tab");
  const tab: "calendar" | "plan" | "settings" =
    rawTab === "plan" || rawTab === "settings" ? rawTab : "calendar";
  const setTab = useCallback(
    (id: "calendar" | "plan" | "settings") => {
      if (id === "calendar") {
        setPlannerDay(startOfDay(new Date()));
        setCalendarView(Views.DAY);
      }
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          if (id === "calendar") {
            next.delete("tab");
            next.delete("day");
          } else {
            next.set("tab", id);
          }
          return next;
        },
        { replace: true },
      );
    },
    [setSearchParams],
  );
  const [plannerRefresh, setPlannerRefresh] = useState(0);
  const [syncing, setSyncing] = useState(false);
  const [syncHint, setSyncHint] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [exportHint, setExportHint] = useState<string | null>(null);
  const [exportDays, setExportDays] = useState(7);
  const [exportInclude, setExportInclude] = useState({
    summary: true,
    patterns: true,
    by_day: true,
    blocks: true,
    hints: true,
    policy: true,
  });
  const [exportProductiveOnly, setExportProductiveOnly] = useState(false);
  const [proposing, setProposing] = useState(false);
  const [proposed, setProposed] = useState<ProposedPlannerBlock[] | null>(null);
  const [proposeMeta, setProposeMeta] = useState<{
    rationale: string;
    used_llm: boolean;
    scaled_daily_hours?: number;
  } | null>(null);
  const [proposeGoals, setProposeGoals] = useState(() => formatGoalsForPrompt(loadProductivityGoals()));
  const [proposeHorizon, setProposeHorizon] = useState<"day" | "week" | "month" | "custom">("week");
  const [customHorizonDays, setCustomHorizonDays] = useState(14);
  const [planAppliedThisSession, setPlanAppliedThisSession] = useState(false);
  const [hasRoutines, setHasRoutines] = useState(false);
  const [hasTimetableBlocks, setHasTimetableBlocks] = useState(false);
  /** Active Plan-tab step — completed steps stay collapsed on the left rail */
  const [planStep, setPlanStep] = useState<"goals" | "routines" | "propose" | "done" | "sync">("routines");
  const [dayLockedHours, setDayLockedHours] = useState(0);
  /** Goals step only checks off after Save or Next — not because defaults prefill text */
  const [goalsConfirmed, setGoalsConfirmed] = useState(false);

  const onRoutinesChange = useCallback((rows: PlannerRoutine[]) => {
    setHasRoutines(rows.length > 0);
  }, []);

  const goalsDone = goalsConfirmed;
  const routinesDone = hasRoutines || hasTimetableBlocks;
  const proposeDone = Boolean(proposed?.length) || planAppliedThisSession;
  const finishDone = planAppliedThisSession;
  const syncDone = planAppliedThisSession; // last step available after apply
  const planStepOrder = ["routines", "goals", "propose", "done", "sync"] as const;
  const planStepRef = useRef<HTMLDivElement>(null);

  // Do not auto-force planStep here — that blocked Goals/Build/Apply/Watch clicks
  // whenever a draft existed. Advance only from propose/apply success handlers.

  useEffect(() => {
    planStepRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [planStep]);

  useEffect(() => {
    let cancelled = false;
    void fetchDemoClock()
      .then((d) => {
        if (!cancelled) setDemoClock(d);
      })
      .catch(() => {
        if (!cancelled) setDemoClock(null);
      });
    return () => {
      cancelled = true;
    };
  }, [plannerRefresh, lastRefresh]);

  useEffect(() => {
    const raw = searchParams.get("day");
    if (!raw || !/^\d{4}-\d{2}-\d{2}$/.test(raw)) return;
    const [y, m, d] = raw.split("-").map(Number);
    const next = new Date(y, m - 1, d, 12, 0, 0, 0);
    setPlannerDay((prev) =>
      prev.getFullYear() === next.getFullYear() &&
      prev.getMonth() === next.getMonth() &&
      prev.getDate() === next.getDate()
        ? prev
        : next,
    );
  }, [searchParams]);

  useEffect(() => {
    let cancelled = false;
    const from = startOfDay(plannerDay);
    const to = endOfDay(plannerDay);
    void fetchPlannerBlocks(from, to)
      .then((rows) => {
        if (cancelled) return;
        const mins = rows
          .filter((b) => b.status !== "rolled")
          .reduce((sum, b) => {
            const a = new Date(b.start_at).getTime();
            const e = new Date(b.end_at).getTime();
            return sum + Math.max(0, (e - a) / 60_000);
          }, 0);
        setDayLockedHours(mins / 60);
      })
      .catch(() => {
        if (!cancelled) setDayLockedHours(0);
      });
    return () => {
      cancelled = true;
    };
  }, [plannerDay, plannerRefresh]);

  const horizonDays =
    proposeHorizon === "day" ? 1 : proposeHorizon === "week" ? 7 : proposeHorizon === "month" ? 30 : customHorizonDays;

  /** Always start from today — never propose / plan days already in the past. */
  const proposeRangeStart = useMemo(() => {
    const today = new Date();
    const y = today.getFullYear();
    const m = String(today.getMonth() + 1).padStart(2, "0");
    const d = String(today.getDate()).padStart(2, "0");
    return `${y}-${m}-${d}`;
  }, [proposeHorizon]);

  const statsView = calendarViewToStats(calendarView);
  const statsRange = useMemo(
    () => statsRangeForView(statsView, plannerDay),
    [statsView, plannerDay.getTime()],
  );
  const adherenceWindow = statsView === "day" ? 7 : statsRange.dayCount;
  const adherenceEnd = statsRange.to;
  const variancePreset = statsView === "day" ? "day" : statsView === "month" ? "month" : "week";

  const loadAdherence = useCallback(async (day: Date) => {
    try {
      const a = await fetchAdherence(day);
      setAdherence(a);
    } catch {
      setAdherence(null);
    }
  }, []);

  const loadDue = useCallback(async () => {
    try {
      const d = await fetchDueReview(5);
      setDueReviews(d.count ?? d.items?.length ?? 0);
    } catch {
      setDueReviews(0);
    }
  }, []);

  const bumpPlanner = useCallback(() => {
    setPlannerRefresh((k) => k + 1);
    void loadAdherence(plannerDay);
    void loadDue();
  }, [plannerDay, loadAdherence, loadDue]);

  useEffect(() => {
    const day = toApiDay(plannerDay);
    void fetchHubDaily(day)
      .then((h) => {
        if (h && (h.sleep_minutes || 0) > 0) setSleepHours(h.sleep_minutes / 60);
        else setSleepHours(null);
      })
      .catch(() => setSleepHours(null));
  }, [plannerDay, plannerRefresh]);

  /** Header + GlanceBar — follow selected month/week/day. */
  const loadCore = useCallback(async () => {
    const results = await Promise.allSettled([
      fetchDesktopStatsForRange(statsRange.from, statsRange.to),
      fetchTrackerHealth(),
    ]);
    const failures: string[] = [];
    if (results[0].status === "fulfilled") setDesktop(results[0].value);
    else {
      failures.push(
        `desktop-stats: ${results[0].reason instanceof Error ? results[0].reason.message : "failed"}`,
      );
    }
    if (results[1].status === "fulfilled") setTrackerHealth(results[1].value);
    else {
      failures.push(
        `tracker-health: ${results[1].reason instanceof Error ? results[1].reason.message : "failed"}`,
      );
    }
    return failures;
  }, [statsRange.from.getTime(), statsRange.to.getTime()]);

  /** Screen-time extras — KPIs detail + timeline for the focused day. */
  const loadScreenTime = useCallback(async () => {
    const timelineDay = toApiDay(plannerDay);
    const results = await Promise.allSettled([
      fetchBrowserStatsForRange(statsRange.from, statsRange.to),
      fetchDesktopTimeline(timelineDay),
    ]);
    const failures: string[] = [];
    if (results[0].status === "fulfilled") setBrowser(results[0].value);
    else {
      failures.push(
        `browser stats: ${results[0].reason instanceof Error ? results[0].reason.message : "failed"}`,
      );
    }
    if (results[1].status === "fulfilled") setTimeline(results[1].value);
    else {
      failures.push(
        `desktop-timeline: ${results[1].reason instanceof Error ? results[1].reason.message : "failed"}`,
      );
    }
    return failures;
  }, [plannerDay.getTime(), statsRange.from.getTime(), statsRange.to.getTime()]);

  /** Full refresh (Sync / Refresh button) — core + screen-time extras. */
  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    setLoadErrors([]);
    const failures = [...(await loadCore()), ...(await loadScreenTime())];
    if (failures.length >= 4) {
      setError(failures[0] ?? "Failed to load stats");
    } else if (failures.length > 0) {
      setLoadErrors(failures);
    }
    setLastRefresh(new Date());
    setLoading(false);
  }, [loadCore, loadScreenTime]);

  const syncTracker = useCallback(async () => {
    setSyncing(true);
    setSyncHint(null);
    try {
      const result = await forceTrackerSync();
      await load();
      void loadAdherence(plannerDay);
      setPlannerRefresh((k) => k + 1);
      void loadDue();
      setSyncHint(
        result.flushed
          ? `Synced · last activity ${result.last_event_at ? new Date(result.last_event_at).toLocaleTimeString() : "now"}`
          : result.message,
      );
      setTimeout(() => setSyncHint(null), 3500);
    } catch (e: unknown) {
      setSyncHint(e instanceof Error ? e.message : "Sync failed");
      setTimeout(() => setSyncHint(null), 4000);
    } finally {
      setSyncing(false);
    }
  }, [load, loadAdherence, loadDue, plannerDay]);

  const exportWeek = useCallback(async (format: "json" | "csv") => {
    setExporting(true);
    setExportHint(null);
    try {
      const include = Object.entries(exportInclude)
        .filter(([, on]) => on)
        .map(([k]) => k)
        .join(",");
      await downloadProductivityWeekExport(exportDays, format, {
        include: include || "summary,patterns,policy",
        productiveOnly: exportProductiveOnly,
      });
      setExportHint(`Downloaded ${exportDays}d ${format.toUpperCase()}`);
    } catch (e: unknown) {
      setExportHint(e instanceof Error ? e.message : "Export failed");
    } finally {
      setExporting(false);
    }
  }, [exportDays, exportInclude, exportProductiveOnly]);

  const runPropose = useCallback(
    async (mode: "smart" | "review" | "full") => {
      setProposing(true);
      setExportHint(null);
      try {
        const draftForReview =
          mode === "review"
            ? (proposed || [])
                .filter((b) => b.source !== "existing")
                .map(({ title, category, start_at, end_at, source }) => ({
                  title,
                  category,
                  start_at,
                  end_at,
                  source: source ?? "study",
                }))
            : undefined;

        const res = await proposeWeekFromExport({
          days: exportDays,
          goals: proposeGoals,
          range_start: proposeRangeStart,
          horizon_days: horizonDays,
          use_llm: mode !== "smart",
          include_routines: true,
          mode,
          draft_blocks: draftForReview?.length ? draftForReview : undefined,
        });
        const from = new Date(`${proposeRangeStart}T00:00:00`);
        const to = new Date(from);
        to.setDate(to.getDate() + horizonDays);

        const [calendarBlocks, routines] = await Promise.all([
          fetchPlannerBlocks(from, to).catch(() => []),
          fetchRoutines().catch(() => []),
        ]);

        const existing: ProposedPlannerBlock[] = calendarBlocks.map((b) => ({
          title: b.title,
          category: b.category,
          start_at: b.start_at,
          end_at: b.end_at,
          source: "existing" as const,
          existing_id: b.id,
        }));

        const proposedFresh = (res.blocks || [])
          .map((b) => ({
            ...b,
            source: (b.source ?? "study") as ProposedPlannerBlock["source"],
          }))
          // Drop drafts already on the calendar (routines applied earlier, etc.)
          .filter((b) => !draftCoveredBySavedBlocks(b, calendarBlocks));

        const hasRoutineFromApi = proposedFresh.some((b) => b.source === "routine");
        const routineBlocks = hasRoutineFromApi
          ? []
          : materializeRoutineBlocks(
              routines.filter((r) => r.enabled),
              proposeRangeStart,
              horizonDays,
            ).filter((r) => !draftCoveredBySavedBlocks(r, calendarBlocks));

        // Keep proposed study/break/routine hours that aren't already saved.
        // Overlay existing calendar only where it doesn't collide with drafts.
        const proposedCore = [
          ...proposedFresh,
          ...routineBlocks.filter((r) => !proposedFresh.some((p) => blocksOverlap(p, r))),
        ];
        const existingOverlay = existing.filter(
          (e) => !proposedCore.some((p) => blocksOverlap(p, e)),
        );
        const mergedRaw = [...proposedCore, ...existingOverlay];
        // Drop anything before today (local) — past days are not plannable.
        const mergedFiltered = mergedRaw.filter((b) => {
          const local = new Date(b.start_at);
          const lk = `${local.getFullYear()}-${String(local.getMonth() + 1).padStart(2, "0")}-${String(local.getDate()).padStart(2, "0")}`;
          return lk >= proposeRangeStart;
        });
        // No overlaps: cascade later blocks (routines/existing keep earlier slots when tied)
        const merged = resolveProposedOverlaps(mergedFiltered);

        setProposed(merged);
        const label =
          horizonDays === 1 ? "day" : horizonDays === 7 ? "week" : horizonDays === 30 ? "month" : `${horizonDays}-day`;
        const nR = merged.filter((b) => proposeBlockStatKind(b) === "routine").length;
        const nB = merged.filter((b) => proposeBlockStatKind(b) === "break").length;
        const nE = merged.filter((b) => b.source === "existing").length;
        const nDraftStudy = merged.filter((b) => b.source === "study").length;
        const studyMin = merged
          .filter((b) => proposeBlockStatKind(b) === "study")
          .reduce((acc, b) => acc + blockDurationMinutes(b), 0);
        const alreadyOnCalendar = merged.length > 0 && nE === merged.length;
        const modeLabel = mode === "review" ? "AI review" : mode === "smart" ? "Smart gap-fill" : "AI propose";

        let rationale = res.rationale;
        if (alreadyOnCalendar) {
          rationale =
            `Plan already on calendar for this ${label} — showing ${merged.length} saved blocks ` +
            `(${(studyMin / 60).toFixed(1)}h study, ${nR} life/routines, ${nB} breaks). ` +
            `Edit on the schedule; Apply skips slots that are already saved.`;
        }

        setProposeMeta({
          rationale,
          used_llm: res.used_llm,
          scaled_daily_hours: res.scaled_daily_hours,
        });
        setPlanStep("propose");
        setExportHint(
          alreadyOnCalendar
            ? `${modeLabel} · ${label}: already on calendar — ${(studyMin / 60).toFixed(1)}h study · ${merged.length} blocks (${nR} life/routines, ${nB} breaks)`
            : `${modeLabel} · ${label}: ${(studyMin / 60).toFixed(1)}h study / goal · ${merged.length} blocks (${nR} routines, ${nB} breaks, ${nE} calendar${nDraftStudy ? `, ${nDraftStudy} new study` : ""})`,
        );
      } catch (e: unknown) {
        setExportHint(e instanceof Error ? e.message : "Propose failed");
      } finally {
        setProposing(false);
      }
    },
    [exportDays, proposeGoals, proposeRangeStart, horizonDays, proposed],
  );

  const applyPropose = useCallback(
    async (range?: { from: string; to: string; label?: string; days?: string[] }) => {
      const todayKey = (() => {
        const t = new Date();
        const y = t.getFullYear();
        const m = String(t.getMonth() + 1).padStart(2, "0");
        const d = String(t.getDate()).padStart(2, "0");
        return `${y}-${m}-${d}`;
      })();
      const from = range?.from ?? todayKey;
      const to = range?.to ?? "9999-12-31";
      const daySet = range?.days?.length ? new Set(range.days) : null;
      const toApply = (proposed || []).filter((b) => {
        if (b.source === "existing") return false;
        const local = new Date(b.start_at);
        const lk = `${local.getFullYear()}-${String(local.getMonth() + 1).padStart(2, "0")}-${String(local.getDate()).padStart(2, "0")}`;
        if (lk < todayKey) return false;
        if (daySet) return daySet.has(lk);
        return lk >= from && lk <= to;
      });
      if (!toApply.length) {
        setExportHint("No editable blocks in that date range");
        return;
      }
      setProposing(true);
      try {
        const res = await applyProposedBlocks(
          toApply.map(({ title, category, start_at, end_at }) => ({
            title,
            category,
            start_at,
            end_at,
          })),
        );
        let gHint = "";
        try {
          const g = await syncPlannerToGoogleCalendar(14);
          if (g.ok) {
            gHint = ` · Google +${g.created ?? 0}/~${g.updated ?? 0}`;
          }
        } catch {
          /* OAuth optional */
        }
        const rangeHint = range?.label ? ` (${range.label})` : "";
        setExportHint(`Applied ${res.created} blocks${rangeHint}${gHint}`);
        setProposed(null);
        setProposeMeta(null);
        setPlanAppliedThisSession(true);
        bumpPlanner();
        setPlanStep("done");
      } catch (e: unknown) {
        setExportHint(e instanceof Error ? e.message : "Apply failed");
      } finally {
        setProposing(false);
      }
    },
    [proposed, bumpPlanner],
  );

  useEffect(() => {
    void loadDue();
  }, [loadDue]);

  // Initial + tab-aware polling: always core; screen-time extras on Calendar (and Settings for overrides).
  useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      if (typeof document !== "undefined" && document.visibilityState === "hidden") return;
      setLoading(true);
      setError(null);
      const failures = [...(await loadCore())];
      if (!cancelled && (tab === "calendar" || tab === "settings")) {
        failures.push(...(await loadScreenTime()));
      }
      if (cancelled) return;
      if (failures.length > 0) {
        const coreOnly = tab === "plan";
        if (!coreOnly && failures.length >= 4) setError(failures[0] ?? "Failed to load stats");
        else if (coreOnly && failures.length >= 2) setError(failures[0] ?? "Failed to load stats");
        else setLoadErrors(failures);
      } else {
        setLoadErrors([]);
      }
      setLastRefresh(new Date());
      setLoading(false);
    };
    void tick();
    const id = setInterval(() => {
      void tick();
    }, 60_000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [loadCore, loadScreenTime, tab]);

  useEffect(() => {
    void loadAdherence(plannerDay);
  }, [plannerDay, loadAdherence]);

  const trackerStatus = trackerHealth?.status ?? (desktop?.tracker_running ? "running" : "no_data");
  const trackerRunning = trackerStatus === "running" || trackerHealth?.process_alive === true;
  const trackerStale = trackerStatus === "stale" && !trackerHealth?.process_alive;
  const maxSec = desktop?.sessions[0]?.seconds ?? 1;
  const totalHours = desktop ? (desktop.total_seconds / 3600).toFixed(1) : "—";
  const avgScore = desktop?.avg_productivity_score ?? 0;

  return (
    <div className="h-full overflow-y-auto bg-background text-foreground px-0 py-0 sm:px-0">
      <div className="w-full max-w-none space-y-5 pb-16">

      {demoClock?.enabled ? (
        <div className="rounded-xl border border-amber-400/40 bg-amber-500/15 px-4 py-2.5 text-sm text-amber-50 flex flex-wrap items-center justify-between gap-2">
          <span>
            Demo clock on —{" "}
            {demoClock.now_iso
              ? new Date(demoClock.now_iso).toLocaleString()
              : demoClock.day || "?"}{" "}
            <span className="text-amber-100/70 text-xs">
              (real data only · no fake productive)
            </span>
          </span>
          <button
            type="button"
            className="text-xs px-2.5 py-1 rounded-md border border-amber-300/40 hover:bg-amber-400/20"
            onClick={() => {
              void clearDemoClock().then((st) => {
                setDemoClock(st);
                setPlannerRefresh((n) => n + 1);
              });
            }}
          >
            Back to real time
          </button>
        </div>
      ) : null}

      {/* Header: tabs + actions (page title lives in AppTopBar) */}
      <div className="gloss-panel rounded-3xl border border-border/50 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="grid grid-cols-3 rounded-xl border border-border/50 bg-background/35 p-1 text-sm">
            {([
              { id: "calendar" as const, label: "Calendar" },
              { id: "plan" as const, label: "Plan" },
              { id: "settings" as const, label: "Settings" },
            ]).map(({ id, label }) => (
              <button
                key={id}
                type="button"
                onClick={() => setTab(id)}
                className={`rounded-lg px-3 py-1.5 text-center transition-colors ${
                  tab === id ? "bg-primary text-primary-foreground shadow-sm" : "text-muted-foreground hover:bg-accent/60 hover:text-foreground"
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          <div className="flex flex-wrap items-center justify-end gap-2">
            <button
              type="button"
              onClick={() => void syncTracker()}
              disabled={syncing || loading}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary text-primary-foreground text-sm transition-colors hover:bg-primary/90 disabled:opacity-50"
              title="Flush the desktop tracker session into the DB, then reload stats"
            >
              <Zap size={13} className={syncing ? "animate-pulse" : ""} />
              Update tracker
            </button>
            <button
              type="button"
              onClick={load}
              disabled={loading}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-background/50 hover:bg-accent/60 text-sm border border-border/50 transition-colors disabled:opacity-50"
              title="Reload planner stats and screen-time data (no tracker flush)"
            >
              <RefreshCw size={13} className={loading ? "animate-spin" : ""} />
              Reload
            </button>
            <span
              {...trackerEgg}
              className={`inline-flex cursor-pointer items-center gap-1 rounded-full border px-2.5 py-1 text-xs select-none ${
                trackerRunning
                  ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
                  : trackerStale
                    ? "border-yellow-500/30 bg-yellow-500/10 text-yellow-300"
                    : "border-orange-500/30 bg-orange-500/10 text-orange-300"
              }`}
              title={[
                trackerRunning
                  ? "Standalone tracker running · long-press…"
                  : trackerStale
                    ? "Tracker data is stale"
                    : "Tracker not installed or no data yet",
                `Refreshed ${lastRefresh.toLocaleTimeString()}`,
                trackerHealth?.last_event_at
                  ? `Last tracked ${new Date(trackerHealth.last_event_at).toLocaleString()}`
                  : null,
              ]
                .filter(Boolean)
                .join(" · ")}
            >
              {trackerRunning ? (
                <CheckCircle2 size={11} className="shrink-0" />
              ) : trackerStale ? (
                <Clock size={11} className="shrink-0" />
              ) : (
                <AlertCircle size={11} className="shrink-0" />
              )}
              {trackerRunning ? "Tracker on" : trackerStale ? "Tracker stale" : "Tracker off"}
            </span>
            {syncHint && (
              <span className="max-w-[220px] truncate rounded-full border border-emerald-500/25 bg-emerald-500/10 px-2.5 py-1 text-xs text-emerald-300" title={syncHint}>
                {syncHint}
              </span>
            )}
            {exportHint && (tab === "plan" || tab === "settings") && (
              <span className="max-w-[220px] truncate rounded-full border border-sky-500/25 bg-sky-500/10 px-2.5 py-1 text-xs text-sky-300" title={exportHint}>
                {exportHint}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Compact setup help only when tracker needs attention */}
      {!trackerRunning && (
        <div className={`flex items-start gap-2.5 rounded-xl border px-3 py-2.5 text-xs ${
          trackerStale
            ? "border-yellow-500/25 bg-yellow-500/5 text-yellow-200/90"
            : "border-orange-500/25 bg-orange-500/5 text-orange-200/90"
        }`}>
          {trackerStale ? (
            <Clock size={13} className="mt-0.5 shrink-0 text-yellow-400" />
          ) : (
            <AlertCircle size={13} className="mt-0.5 shrink-0 text-orange-400" />
          )}
          <div className="min-w-0 space-y-1">
            {trackerStale ? (
              <p>
                Last activity{" "}
                {trackerHealth?.last_event_at
                  ? new Date(trackerHealth.last_event_at).toLocaleString()
                  : "unknown"}
                . Try Update tracker or{" "}
                <code className="rounded bg-black/40 px-1 font-mono">
                  scripts\desktop_tracker\run_desktop_tracker_headless.bat
                </code>
                {trackerHealth?.hint ? ` · ${trackerHealth.hint}` : ""}
              </p>
            ) : (
              <p>
                Run once:{" "}
                <code className="rounded bg-black/40 px-1 font-mono">scripts\install_tracker_startup.bat</code>
                {" "}or{" "}
                <code className="rounded bg-black/40 px-1 font-mono">
                  scripts\desktop_tracker\run_desktop_tracker_headless.bat
                </code>
              </p>
            )}
          </div>
        </div>
      )}

      {error && (
        <div className="flex items-center gap-2 p-3 rounded-xl bg-red-500/10 border border-red-500/30 text-red-300 text-sm">
          <AlertCircle size={14} />
          {error}
        </div>
      )}

      {loadErrors.length > 0 && !error && (
        <div className="flex items-start gap-2 p-3 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-200 text-sm">
          <AlertCircle size={14} className="shrink-0 mt-0.5" />
          <ul className="list-disc list-inside space-y-0.5">
            {loadErrors.map((msg) => (
              <li key={msg}>{msg}</li>
            ))}
          </ul>
        </div>
      )}

      {tab === "calendar" && (
      <div className="space-y-6">
        <GlanceBar
          desktop={desktop}
          dueReviews={dueReviews}
          rangeLabel={statsRange.label}
          sleepHours={sleepHours}
          onScheduleReview={() => {
            const start = new Date(plannerDay);
            if (toApiDay(plannerDay) === toApiDay(new Date())) {
              start.setMinutes(start.getMinutes() + 15 - (start.getMinutes() % 15));
            } else {
              start.setHours(9, 0, 0, 0);
            }
            void createPlannerBlock({
              title: "SRS review",
              category: "review",
              start_at: start.toISOString(),
              duration_minutes: Math.min(30, 15 + dueReviews * 2),
            }).then(() => bumpPlanner());
          }}
        />

        <div className="w-full bg-white/[0.03] border border-white/10 rounded-2xl p-5 sm:p-6">
          <PlannerCalendar
            expanded
            refreshKey={plannerRefresh}
            selectedDay={plannerDay}
            onSelectedDayChange={setPlannerDay}
            view={calendarView}
            onViewChange={setCalendarView}
            headerTitle={
              <h2 className="planner-cal-header__title">
                <CalendarDays size={16} className="planner-cal-header__title-icon" aria-hidden />
                Planner calendar
              </h2>
            }
            headerBadge={
              adherence ? (
                <span
                  className="planner-cal-header__kpi"
                  title="Effective focus for the selected day (planned ∩ productive)"
                >
                  On-plan {(adherence.effective_focus_minutes / 60).toFixed(1)}h
                  {adherence.planned_minutes > 0
                    ? ` · ${Math.round((adherence.adherence_pct ?? 0))}% plan`
                    : ""}
                </span>
              ) : null
            }
          />
        </div>

        <div className="space-y-5 rounded-2xl border border-white/10 bg-white/[0.03] p-5 sm:p-6">
          <PlanVsActualDashboard
            selectedDay={plannerDay}
            onSelectedDayChange={setPlannerDay}
            refreshKey={plannerRefresh}
            trackerHealth={trackerHealth}
            adherenceDays={adherenceWindow}
            adherenceEnd={adherenceEnd}
            variancePreset={variancePreset}
          />
        </div>

        <details className="group rounded-2xl border border-white/10 bg-white/[0.03] open:pb-4">
          <summary className="cursor-pointer list-none flex items-center gap-2 px-5 py-3.5 text-sm font-medium text-muted-foreground hover:text-foreground">
            <ChevronRight size={14} className="transition-transform group-open:rotate-90 text-primary" />
            Screen time details
            <span className="text-[10px] font-normal opacity-70">apps, browser, timeline · {statsRange.label}</span>
          </summary>
          <div className="px-5 space-y-6">
            <div className="bg-black/20 border border-white/10 rounded-2xl p-5">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-semibold flex items-center gap-2 text-sm">
                  <Monitor size={15} className="text-primary" />
                  Desktop App Usage
                </h3>
                {desktop && (
                  <span className="tabular-nums text-xs text-muted-foreground">
                    {fmtSeconds(desktop.total_seconds)} · {statsRange.label}
                  </span>
                )}
              </div>

              {loading && !desktop && (
                <div className="space-y-3">
                  {[...Array(5)].map((_, i) => (
                    <div key={i} className="h-9 rounded-lg bg-white/5 animate-pulse" />
                  ))}
                </div>
              )}

              {!loading && (!desktop?.sessions || desktop.sessions.length === 0) && (
                <div className="text-center py-8 text-muted-foreground text-sm space-y-2">
                  <Monitor size={28} className="mx-auto opacity-30" />
                  <p>No desktop data yet.</p>
                  <code className="block bg-black/40 px-3 py-1.5 rounded-lg text-xs font-mono mx-auto w-fit">
                    scripts\install_tracker_startup.bat
                  </code>
                </div>
              )}

              {timeline && timeline.intervals.length > 0 && (
                <div className="mb-6 pb-6 border-b border-white/5">
                  <div className="text-xs text-muted-foreground mb-3 uppercase tracking-wider">
                    Timeline · {plannerDay.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" })}
                  </div>
                  <DayTimeline
                    timeline={timeline}
                    listTotalSeconds={statsView === "day" ? desktop?.total_seconds : timeline?.total_seconds}
                  />
                </div>
              )}

              {desktop?.sessions && desktop.sessions.length > 0 && (
                <div className="divide-y divide-white/5">
                  {desktop.sessions.map((s) =>
                    s.kind === "browser" && s.sites && s.sites.length > 0 ? (
                      <BrowserGroupRow key={s.exe} session={s} maxSeconds={maxSec} />
                    ) : (
                      <AppRow key={s.exe} session={s} maxSeconds={maxSec} />
                    ),
                  )}
                </div>
              )}
            </div>

            <div className="bg-black/20 border border-white/10 rounded-2xl p-5">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-semibold flex items-center gap-2 text-sm">
                  <Globe size={15} className="text-sky-400" />
                  Browser Activity
                </h3>
                <div className="flex items-center gap-3 text-xs text-muted-foreground">
                  {browser?.avg_productivity_score != null && browser.avg_productivity_score > 0 && (
                    <span className={`font-bold text-sm ${scoreColor(browser.avg_productivity_score)}`}>
                      {browser.avg_productivity_score}
                      <span className="font-normal text-[10px] text-muted-foreground ml-0.5">/ 100</span>
                    </span>
                  )}
                </div>
              </div>

              {browser && browser.events_today > 0 ? (
                <>
                  {Object.keys(browser.category_breakdown).length > 0 && (
                    <div className="mb-5">
                      <div className="text-xs text-muted-foreground mb-2 uppercase tracking-wider">Categories (by time)</div>
                      <div className="flex flex-wrap gap-2">
                        {Object.entries(browser.category_breakdown)
                          .sort(([, a], [, b]) => b - a)
                          .map(([cat, seconds]) => (
                            <span
                              key={cat}
                              className="px-2.5 py-1 rounded-full bg-white/5 border border-white/10 text-xs"
                            >
                              {cat} <span className="text-muted-foreground">·{fmtSeconds(seconds)}</span>
                            </span>
                          ))}
                      </div>
                    </div>
                  )}

                  {browser.top_domains.length > 0 && (
                    <div>
                      <div className="text-xs text-muted-foreground mb-2 uppercase tracking-wider">Top Sites</div>
                      <div className="space-y-1.5">
                        {browser.top_domains.slice(0, 10).map((d) => {
                          const domainScore = d.productivity_score ?? 35;
                          return (
                            <div key={d.domain} className="flex items-center gap-3">
                              <span className="text-sm w-44 min-w-0 truncate" title={d.domain}>{d.domain}</span>
                              <div className="flex-1 relative h-5 rounded-full bg-white/5 overflow-hidden">
                                <div
                                  className={`h-full rounded-full ${scoreBg(domainScore)} opacity-80 transition-all duration-500`}
                                  style={{
                                    width: `${Math.min(100, (d.seconds / (browser.top_domains[0]?.seconds || 1)) * 100)}%`,
                                  }}
                                />
                              </div>
                              <span className="text-xs text-muted-foreground w-14 text-right tabular-nums">
                                {fmtSeconds(d.seconds)}
                              </span>
                              <span className="text-[10px] text-muted-foreground w-28 text-right truncate" title={d.category}>
                                {d.category || "Other"}
                              </span>
                              <span className={`text-xs font-semibold w-8 text-right tabular-nums ${scoreColor(domainScore)}`}>
                                {domainScore}
                              </span>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </>
              ) : (
                <div className="text-center py-6 text-muted-foreground text-sm space-y-2">
                  <Globe size={24} className="mx-auto opacity-30" />
                  <p>No browser data yet for this range.</p>
                </div>
              )}
            </div>
          </div>
        </details>
      </div>
      )}

      {tab === "plan" && (
      <div className="grid gap-5 xl:grid-cols-2 items-start">
        {/* Left: planning steps */}
        <div className="flex min-w-0 flex-col gap-3 xl:sticky xl:top-3 xl:h-[calc(100vh-5.5rem)] xl:max-h-[calc(100vh-5.5rem)]">
          <div className="shrink-0 rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2.5 space-y-1">
            <h2 className="text-sm font-semibold text-foreground">Today’s plan</h2>
            <p className="text-[11px] text-muted-foreground">
              Work the steps below · confirm morning plan when ready · browser stays STUDY until free
              time / break blocks.
            </p>
          </div>
          <nav aria-label="Plan steps" className="shrink-0 px-1 pt-0.5 pb-0.5">
            <ol className="relative grid grid-cols-5">
              <div
                aria-hidden
                className="pointer-events-none absolute left-[10%] right-[10%] top-[9px] h-px bg-white/15"
              />
              <div
                aria-hidden
                className="pointer-events-none absolute left-[10%] top-[9px] h-px bg-emerald-500/70 transition-[width] duration-300"
                style={{
                  width: `${Math.max(0, planStepOrder.indexOf(planStep)) * 20}%`,
                }}
              />
              {(
                [
                  { id: "routines" as const, n: 1, label: "Routines", done: routinesDone },
                  { id: "goals" as const, n: 2, label: "Goals", done: goalsDone },
                  { id: "propose" as const, n: 3, label: "Build", done: proposeDone },
                  { id: "done" as const, n: 4, label: "Apply", done: finishDone },
                  { id: "sync" as const, n: 5, label: "Watch", done: syncDone && planStep === "sync" },
                ] as const
              ).map((s) => {
                const active = planStep === s.id;
                return (
                  <li key={s.id} className="relative z-[1] flex justify-center">
                    <button
                      type="button"
                      onClick={() => setPlanStep(s.id)}
                      aria-current={active ? "step" : undefined}
                      className="flex flex-col items-center gap-1 min-w-0"
                    >
                      <span
                        className={`flex h-[18px] w-[18px] items-center justify-center rounded-full border text-[9px] font-semibold transition-colors ${
                          s.done
                            ? "border-emerald-500 bg-emerald-500 text-white"
                            : active
                              ? "border-primary bg-primary text-primary-foreground ring-2 ring-primary/30"
                              : "border-white/25 bg-background text-muted-foreground"
                        }`}
                      >
                        {s.done ? <CheckCircle2 size={11} /> : s.n}
                      </span>
                      <span
                        className={`text-[10px] leading-none ${
                          active
                            ? "font-semibold text-foreground"
                            : s.done
                              ? "text-emerald-200/90"
                              : "text-muted-foreground"
                        }`}
                      >
                        {s.label}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ol>
          </nav>

          <div
            ref={planStepRef}
            className="min-h-0 flex-1 overflow-y-auto overscroll-contain pr-1 space-y-3"
          >
          {planStep === "routines" && (
            <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 space-y-4">
              <div>
                <h2 className="text-sm font-semibold text-foreground">1 · Routines</h2>
                <p className="text-xs text-muted-foreground mt-1">
                  Lock fixed times first (meals, workout, devotion). The day list on the right updates as you apply.
                </p>
              </div>
              <div className="space-y-4">
                <div className="rounded-xl border border-white/10 bg-black/20 p-4">
                  <RoutinesPanel onApplied={bumpPlanner} onRoutinesChange={onRoutinesChange} />
                </div>
                <details open className="rounded-xl border border-white/10 bg-black/20 open:pb-1">
                  <summary className="cursor-pointer list-none px-4 py-3 text-xs font-medium text-muted-foreground hover:text-foreground">
                    Weekly timetable (optional)
                  </summary>
                  <div className="px-4 pb-4">
                    <TimetablePanel
                      onPlannerUpdated={() => {
                        bumpPlanner();
                        setHasTimetableBlocks(true);
                      }}
                    />
                  </div>
                </details>
              </div>
            </div>
          )}

          {planStep === "goals" && (
            <div className="space-y-3">
              <ProductivityGoalsPanel
                adherence={adherence}
                lockedHours={dayLockedHours}
                onGoalsTextChange={(text) => setProposeGoals(text)}
                onConfirmed={() => setGoalsConfirmed(true)}
              />
            </div>
          )}

          {planStep === "propose" && (
              <ProposeStepPanel
                horizon={proposeHorizon}
                onHorizonChange={setProposeHorizon}
                customHorizonDays={customHorizonDays}
                onCustomHorizonDaysChange={setCustomHorizonDays}
                horizonDays={horizonDays}
                rangeStart={proposeRangeStart}
                exportDays={exportDays}
                onExportDaysChange={setExportDays}
                proposing={proposing}
                onGenerate={(mode) => void runPropose(mode)}
                exportHint={exportHint}
                proposed={proposed}
                proposeMeta={proposeMeta}
                onProposedChange={setProposed}
                onApply={(range) => void applyPropose(range)}
                onDismissDraft={() => {
                  setProposed(null);
                  setProposeMeta(null);
                }}
              />
          )}

          {planStep === "done" && (
            <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 space-y-4">
              <div>
                <h2 className="text-sm font-semibold text-foreground">4 · Apply</h2>
              </div>
              {finishDone ? (
                <div className="space-y-3">
                  <p className="text-sm text-emerald-200">
                    Your schedule is on the calendar. Next: push it to Google so Amazfit can see it.
                  </p>
                  {exportHint ? (
                    <p className="text-xs text-sky-300 break-words" title={exportHint}>{exportHint}</p>
                  ) : null}
                  <div className="grid grid-cols-2 gap-2">
                    <button
                      type="button"
                      onClick={() => setPlanStep("propose")}
                      className="rounded-xl border border-white/10 px-3 py-2.5 text-xs hover:bg-white/5"
                    >
                      Build again
                    </button>
                    <button
                      type="button"
                      onClick={() => setPlanStep("sync")}
                      className="rounded-xl bg-primary px-3 py-2.5 text-xs text-primary-foreground hover:bg-primary/90"
                    >
                      Next · Watch sync
                    </button>
                  </div>
                </div>
              ) : proposed?.length ? (
                <div className="space-y-3">
                  <p className="text-sm text-foreground">
                    Draft ready · {proposed.length} block{proposed.length === 1 ? "" : "s"}. Open Build
                    and use Apply to write them to the calendar.
                  </p>
                  <button
                    type="button"
                    onClick={() => setPlanStep("propose")}
                    className="rounded-xl bg-primary px-4 py-2.5 text-xs font-medium text-primary-foreground hover:bg-primary/90"
                  >
                    Open Build to apply
                  </button>
                </div>
              ) : (
                <div className="space-y-3">
                  <p className="text-sm text-muted-foreground">
                    Nothing applied yet. Generate a draft in Build, then apply it to the calendar.
                  </p>
                  <button
                    type="button"
                    onClick={() => setPlanStep("propose")}
                    className="rounded-xl bg-primary px-4 py-2.5 text-xs font-medium text-primary-foreground hover:bg-primary/90"
                  >
                    Go to Build
                  </button>
                </div>
              )}
            </div>
          )}

          {planStep === "sync" && (
            <div className="space-y-3">
              <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 space-y-2">
                <h2 className="text-sm font-semibold text-foreground">5 · Watch (Google → Amazfit)</h2>
                <p className="text-xs text-muted-foreground">
                  Last planning step — push today&apos;s blocks to Google Calendar so Zepp/Amazfit can show them.
                </p>
                {finishDone ? (
                  <p className="text-xs text-emerald-200/90">Schedule already applied — sync when ready.</p>
                ) : (
                  <p className="text-xs text-amber-200/90">Apply a schedule in step 4 first for a full push.</p>
                )}
              </div>
              <GoogleCalendarSyncPanel refreshKey={plannerRefresh} />
            </div>
          )}

          </div>

          {/* Sticky step footer — always visible in the left column */}
          <div className="shrink-0 flex flex-wrap items-center justify-between gap-2 rounded-xl border border-white/10 bg-background/90 backdrop-blur-sm px-3 py-2.5">
            {planStep === "routines" ? (
              <>
                <span className="text-[11px] text-muted-foreground">Lock times, then set focus hours</span>
                <button
                  type="button"
                  onClick={() => setPlanStep("goals")}
                  className="rounded-xl bg-primary px-4 py-2 text-xs font-medium text-primary-foreground hover:bg-primary/90"
                >
                  Next · Goals
                </button>
              </>
            ) : planStep === "goals" ? (
              <>
                <button
                  type="button"
                  onClick={() => setPlanStep("routines")}
                  className="rounded-xl border border-white/10 px-4 py-2 text-xs hover:bg-white/5"
                >
                  Back
                </button>
                <div className="flex items-center gap-2">
                  <Link to="/journal" className="text-xs text-primary hover:underline inline-flex items-center gap-1">
                    <PenLine size={12} /> Journal
                  </Link>
                  <button
                    type="button"
                    onClick={() => {
                      setGoalsConfirmed(true);
                      setPlanStep("propose");
                    }}
                    className="rounded-xl bg-primary px-4 py-2 text-xs font-medium text-primary-foreground hover:bg-primary/90"
                  >
                    Next · Build
                  </button>
                </div>
              </>
            ) : planStep === "propose" ? (
              <>
                <button
                  type="button"
                  onClick={() => setPlanStep("goals")}
                  className="rounded-xl border border-white/10 px-4 py-2 text-xs hover:bg-white/5"
                >
                  Back
                </button>
                {proposed?.length ? (
                  <button
                    type="button"
                    disabled={proposing}
                    onClick={() =>
                      void applyPropose(
                        applyRangeForHorizon(proposeRangeStart, horizonDays, proposeHorizon),
                      )
                    }
                    className="rounded-xl bg-primary px-4 py-2 text-xs font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                  >
                    {proposing
                      ? "Applying…"
                      : proposeHorizon === "day"
                        ? "Apply today"
                        : proposeHorizon === "week"
                          ? "Apply this week"
                          : proposeHorizon === "month"
                            ? "Apply this month"
                            : `Apply ${horizonDays} days`}
                  </button>
                ) : (
                  <span className="text-[11px] text-muted-foreground">Generate a schedule to continue</span>
                )}
              </>
            ) : planStep === "done" ? (
              <>
                <button
                  type="button"
                  onClick={() => setPlanStep("propose")}
                  className="rounded-xl border border-white/10 px-4 py-2 text-xs hover:bg-white/5"
                >
                  Back
                </button>
                <button
                  type="button"
                  onClick={() => setPlanStep("sync")}
                  className="rounded-xl bg-primary px-4 py-2 text-xs font-medium text-primary-foreground hover:bg-primary/90"
                >
                  Next · Watch
                </button>
              </>
            ) : (
              <>
                <button
                  type="button"
                  onClick={() => setPlanStep(finishDone ? "done" : "propose")}
                  className="rounded-xl border border-white/10 px-4 py-2 text-xs hover:bg-white/5"
                >
                  Back
                </button>
                <button
                  type="button"
                  onClick={() => setTab("calendar")}
                  className="rounded-xl bg-primary px-4 py-2 text-xs font-medium text-primary-foreground hover:bg-primary/90"
                >
                  See tracking
                </button>
              </>
            )}
          </div>
        </div>

        {/* Right: planning calendar */}
        <div className="min-w-0 rounded-2xl border border-white/10 bg-white/[0.03] p-4 xl:sticky xl:top-3 xl:max-h-[calc(100vh-5.5rem)] xl:overflow-y-auto space-y-3">
          <div className="flex items-center justify-between gap-2 px-0.5">
            <div>
              <h2 className="text-sm font-semibold text-foreground">Schedule preview</h2>
              <p className="text-[11px] text-muted-foreground mt-0.5">
                {proposed?.length
                  ? "Day timeline · dashed = draft · edit / move / delete on each block"
                  : "Today’s blocks live here — generate a schedule, draft auto plan, or click an hour to add."}
              </p>
            </div>
          </div>
          <PlannerCalendar
            expanded
            planningOnly
            refreshKey={plannerRefresh}
            selectedDay={plannerDay}
            onSelectedDayChange={setPlannerDay}
            view={calendarView}
            onViewChange={setCalendarView}
            draftBlocks={proposed}
            onDraftBlocksChange={setProposed}
          />
        </div>
      </div>
      )}

      {tab === "settings" && (
      <div className="space-y-8">
        <div className="rounded-xl border border-white/10 bg-white/[0.03] px-4 py-3 text-sm text-muted-foreground">
          <p className="font-medium text-foreground text-xs uppercase tracking-wider mb-1">Settings</p>
          Planning prefs, tracker scoring, wearables, reminders, and exports — grouped below.
          <p className="text-[11px] mt-2">
            <a href="#demo-mode" className="text-amber-200 underline underline-offset-2 hover:text-white">
              Demo mode
            </a>
            {" "}
            (time travel for Soft-land / blocking demos) is further down this tab.
          </p>
        </div>

        <section className="space-y-3">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Planning
          </h2>
          <div className="bg-white/[0.03] border border-white/10 rounded-2xl p-6">
            <PlanningSettingsPanel
              refreshKey={plannerRefresh}
              onPlannerChange={bumpPlanner}
            />
          </div>
        </section>

        <section id="demo-mode" className="space-y-3 scroll-mt-24">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-amber-200/90">
            Demo mode
          </h2>
          <div className="bg-white/[0.03] border border-white/10 rounded-2xl p-6">
            <DemoModePanel
              onChanged={() => {
                setPlannerRefresh((n) => n + 1);
                void fetchDemoClock()
                  .then(setDemoClock)
                  .catch(() => setDemoClock(null));
              }}
              onJumpToDay={(day) => {
                setPlannerDay(day);
                setSearchParams(
                  (prev) => {
                    const next = new URLSearchParams(prev);
                    next.delete("tab");
                    const y = day.getFullYear();
                    const m = String(day.getMonth() + 1).padStart(2, "0");
                    const d = String(day.getDate()).padStart(2, "0");
                    next.set("day", `${y}-${m}-${d}`);
                    return next;
                  },
                  { replace: true },
                );
                setCalendarView(Views.DAY);
              }}
            />
          </div>
        </section>

        <section className="space-y-3">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Wearables
          </h2>
          <div className="bg-white/[0.03] border border-white/10 rounded-2xl p-6">
            <WearablesSyncPanel />
          </div>
        </section>

        <section className="space-y-3">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Plan reminders
          </h2>
          <div className="bg-white/[0.03] border border-white/10 rounded-2xl p-6">
            <PlannerRemindersPanel />
          </div>
        </section>

        <section className="space-y-3">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Scoring & classification
          </h2>
          <div className="bg-white/[0.03] border border-white/10 rounded-2xl p-6">
            <ProductivityPolicyPanel onSaved={() => void load()} />
          </div>
          <div className="bg-white/[0.03] border border-white/10 rounded-2xl p-6">
            <SessionOverridePanel
              timeline={timeline}
              onSaved={() => {
                void load();
                setPlannerRefresh((k) => k + 1);
              }}
            />
          </div>
          <div className="bg-white/[0.03] border border-white/10 rounded-2xl p-6">
            <ClassificationReview trackerNoData={trackerStatus === "no_data"} />
          </div>
        </section>

        <section className="space-y-3">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Export data</h2>
          <div className="bg-white/[0.03] border border-white/10 rounded-2xl p-6 space-y-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h3 className="font-semibold flex items-center gap-2 text-sm">
                  <Download size={16} className="text-primary" />
                  Week export
                </h3>
                <p className="mt-1 text-sm text-muted-foreground">
                  Download productivity data as JSON or CSV (also used as context for AI propose).
                </p>
              </div>
              {exportHint && (
                <span className="max-w-xs truncate rounded-full border border-sky-500/25 bg-sky-500/10 px-3 py-1 text-xs text-sky-300" title={exportHint}>
                  {exportHint}
                </span>
              )}
            </div>

            <div className="grid gap-4 lg:grid-cols-2">
              <div className="space-y-4">
                <div className="grid gap-3 sm:grid-cols-2">
                  <label className="space-y-1 text-xs text-muted-foreground">
                    Date range
                    <div className="flex items-center gap-2 rounded-xl border border-white/10 bg-black/20 px-3 py-2">
                      <span>Last</span>
                      <input
                        type="number"
                        min={1}
                        max={31}
                        value={exportDays}
                        onChange={(e) => setExportDays(Math.max(1, Math.min(31, Number(e.target.value) || 7)))}
                        className="w-14 rounded border border-white/10 bg-black/30 px-2 py-1 text-foreground"
                      />
                      <span>days</span>
                    </div>
                  </label>
                  <label className="flex items-center justify-between gap-3 rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-sm">
                    <span>
                      <span className="block font-medium">Productive only</span>
                      <span className="text-xs text-muted-foreground">Skip distracting sessions.</span>
                    </span>
                    <input
                      type="checkbox"
                      checked={exportProductiveOnly}
                      onChange={(e) => setExportProductiveOnly(e.target.checked)}
                    />
                  </label>
                </div>
                <div>
                  <p className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                    Include sections
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {(["summary", "patterns", "by_day", "blocks", "hints", "policy"] as const).map((k) => (
                      <label
                        key={k}
                        className={`flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs transition-colors ${
                          exportInclude[k]
                            ? "border-primary/30 bg-primary/10 text-primary"
                            : "border-white/10 bg-black/20 text-muted-foreground"
                        }`}
                      >
                        <input
                          type="checkbox"
                          checked={exportInclude[k]}
                          onChange={() => setExportInclude((prev) => ({ ...prev, [k]: !prev[k] }))}
                        />
                        {k.replace("_", " ")}
                      </label>
                    ))}
                  </div>
                </div>
              </div>
              <div className="flex flex-col gap-2 justify-center">
                <button
                  type="button"
                  disabled={exporting}
                  onClick={() => void exportWeek("json")}
                  className="flex items-center justify-center gap-1.5 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-xs hover:bg-white/10 disabled:opacity-50"
                >
                  {exporting ? <Loader2 size={13} className="animate-spin" /> : <Download size={13} />}
                  Export JSON
                </button>
                <button
                  type="button"
                  disabled={exporting}
                  onClick={() => void exportWeek("csv")}
                  className="flex items-center justify-center gap-1.5 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-xs hover:bg-white/10 disabled:opacity-50"
                >
                  <Download size={13} />
                  Export CSV
                </button>
              </div>
            </div>
          </div>
        </section>

        <section className="space-y-3">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Tracker setup</h2>
          <div className="bg-white/[0.03] border border-white/10 rounded-2xl p-6 space-y-3">
            <h3 className="font-semibold flex items-center gap-2 text-sm">
              <Terminal size={15} className="text-sky-400" />
              Edge SelfTracker
            </h3>
            <p className="text-[11px] text-muted-foreground leading-relaxed">
              Study browsing is <strong className="text-foreground/85">Microsoft Edge only</strong>. Load the
              extension, then keep Policy Armed / day mode STUDY so YouTube and other browsers soft-lock.
            </p>
            <ol className="space-y-2 text-sm text-muted-foreground list-decimal list-inside">
              <li>
                Open <code className="bg-black/40 px-1.5 py-0.5 rounded text-xs font-mono">edge://extensions</code>{" "}
                → Developer mode → Load unpacked →{" "}
                <code className="bg-black/40 px-1.5 py-0.5 rounded text-xs font-mono">selftracker-extension/</code>
              </li>
              <li>
                Or run{" "}
                <code className="bg-black/40 px-1.5 py-0.5 rounded text-xs font-mono">
                  scripts\launch_selftracker_edge.bat
                </code>
              </li>
              <li>
                After code updates: <strong className="text-foreground/85">Reload</strong> the extension (v1.5.3+)
              </li>
              <li>
                Chrome / Firefox / installers → soft-lock + Jarvis while enforcing (never killed)
              </li>
            </ol>
          </div>
          <div className="bg-white/[0.03] border border-white/10 rounded-2xl p-6 space-y-3">
            <h3 className="font-semibold flex items-center gap-2 text-sm">
              <Terminal size={15} className="text-green-400" />
              Desktop tracker
            </h3>
            <ol className="space-y-2 text-sm text-muted-foreground list-decimal list-inside">
              <li>Install at logon: <code className="bg-black/40 px-1.5 py-0.5 rounded text-xs font-mono">scripts\install_tracker_startup.bat</code></li>
              <li>Headless now: <code className="bg-black/40 px-1.5 py-0.5 rounded text-xs font-mono">scripts\desktop_tracker\run_desktop_tracker_headless.bat</code></li>
            </ol>
          </div>
        </section>
      </div>
      )}

    </div>
    </div>
  );
}

export default ProductivityPage;
