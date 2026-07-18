import { useState, useEffect, useCallback, useMemo, type ReactNode } from "react";
import {
  Monitor, Globe, RefreshCw, AlertCircle, CheckCircle2,
  Clock, Zap, BarChart2, Terminal, Code2, BookOpen, PenLine,
  Gamepad2, Music, MessageSquare, FileText, Folder, Cpu, CalendarDays,
  ChevronDown, ChevronRight, Download, Loader2,
} from "lucide-react";
import { Views, type View } from "react-big-calendar";
import { fetchDesktopStats, fetchBrowserStats, fetchTrackerHealth, fetchDesktopTimeline, forceTrackerSync } from "../api/behaviorClient";
import type { DesktopStats, BrowserStats, AppSession, BrowserSite, BrowserDomain, TrackerHealth, DesktopTimeline } from "../api/behaviorClient";
import { PlannerCalendar } from "../components/productivity/PlannerCalendar";
import { CalendarInfographics } from "../components/productivity/CalendarInfographics";
import { PlanVsActualDashboard } from "../components/productivity/PlanVsActualDashboard";
import { TimetablePanel } from "../components/productivity/TimetablePanel";
import { TodayPanel } from "../components/productivity/TodayPanel";
import { RoutinesPanel } from "../components/productivity/RoutinesPanel";
import { ProposePlanPreview } from "../components/productivity/ProposePlanPreview";
import { resolveProposedOverlaps } from "../components/productivity/resolveProposedOverlaps";
import { Link } from "react-router";
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
  type CalendarStatsView,
} from "../components/productivity/planVsActualUtils";

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

// ── Score ring SVG ────────────────────────────────────────────────────────────

function ScoreRing({ score, size = 100 }: { score: number; size?: number }) {
  const r = (size - 16) / 2;
  const circ = 2 * Math.PI * r;
  const dash = (score / 100) * circ;
  const col =
    score >= 80 ? "#34d399" :
    score >= 60 ? "#4ade80" :
    score >= 40 ? "#facc15" :
    score >= 20 ? "#fb923c" : "#f87171";

  return (
    <svg width={size} height={size} className="rotate-[-90deg]">
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth={8} />
      <circle
        cx={size / 2} cy={size / 2} r={r}
        fill="none"
        stroke={col}
        strokeWidth={8}
        strokeDasharray={`${dash} ${circ - dash}`}
        strokeLinecap="round"
        style={{ transition: "stroke-dasharray 0.6s ease" }}
      />
    </svg>
  );
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
      <div className="flex items-center gap-2 w-36 min-w-0">
        <Globe size={12} className="text-sky-400 shrink-0" />
        <span className="text-xs truncate text-muted-foreground" title={site.site}>{site.site}</span>
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
  const [plannerDay, setPlannerDay] = useState(new Date());
  const [calendarView, setCalendarView] = useState<View>(Views.WEEK);
  const [tab, setTab] = useState<"calendar" | "plan" | "settings">("calendar");
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
  const [planStep, setPlanStep] = useState<"goals" | "routines" | "propose" | "done">("goals");

  const onRoutinesChange = useCallback((rows: PlannerRoutine[]) => {
    setHasRoutines(rows.length > 0);
  }, []);

  const goalsDone = Boolean(proposeGoals.trim());
  const routinesDone = hasRoutines || hasTimetableBlocks;
  const proposeDone = Boolean(proposed?.length) || planAppliedThisSession;
  const finishDone = planAppliedThisSession;

  useEffect(() => {
    if (planAppliedThisSession) setPlanStep("done");
    else if (proposed?.length) setPlanStep("propose");
  }, [proposed?.length, planAppliedThisSession]);

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

  /** Header + CalendarInfographics — follow selected month/week/day. */
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

        const proposedFresh = (res.blocks || []).map((b) => ({
          ...b,
          source: (b.source ?? "study") as ProposedPlannerBlock["source"],
        }));

        const hasRoutineFromApi = proposedFresh.some((b) => b.source === "routine");
        const routineBlocks = hasRoutineFromApi
          ? []
          : materializeRoutineBlocks(
              routines.filter((r) => r.enabled),
              proposeRangeStart,
              horizonDays,
            );

        // Keep all proposed study/break/routine hours (matches step-1 targets).
        // Overlay existing calendar only where it doesn't collide.
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
        setProposeMeta({
          rationale: res.rationale,
          used_llm: res.used_llm,
          scaled_daily_hours: res.scaled_daily_hours,
        });
        setPlanStep("propose");
        const label =
          horizonDays === 1 ? "day" : horizonDays === 7 ? "week" : horizonDays === 30 ? "month" : `${horizonDays}-day`;
        const nR = merged.filter((b) => b.source === "routine").length;
        const nE = merged.filter((b) => b.source === "existing").length;
        const nB = merged.filter((b) => b.source === "break").length;
        const studyMin = merged
          .filter((b) => b.source === "study")
          .reduce(
            (acc, b) =>
              acc +
              Math.max(
                0,
                Math.round(
                  (new Date(b.end_at).getTime() - new Date(b.start_at).getTime()) / 60_000,
                ),
              ),
            0,
          );
        const modeLabel = mode === "review" ? "AI review" : mode === "smart" ? "Smart gap-fill" : "AI propose";
        setExportHint(
          `${modeLabel} · ${label}: ${(studyMin / 60).toFixed(1)}h study / goal · ${merged.length} blocks (${nR} routines, ${nB} breaks, ${nE} calendar)`,
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
    <div className="h-full overflow-y-auto bg-background text-foreground p-6">
      <div className="mx-auto w-full max-w-7xl space-y-6 pb-20">

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
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="col-span-2 md:col-span-1 bg-white/[0.03] border border-white/10 rounded-2xl p-5 flex flex-col items-center gap-2">
            <div className="relative">
              <ScoreRing score={avgScore} size={88} />
              <div className="absolute inset-0 flex items-center justify-center flex-col">
                <span className={`text-2xl font-bold ${scoreColor(avgScore)}`}>{avgScore}</span>
                <span className="text-[10px] text-muted-foreground">/ 100</span>
              </div>
            </div>
            <div className="text-center">
              <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Productivity Score
              </div>
              <div className="text-xs text-muted-foreground mt-0.5">weighted by time · {statsRange.label}</div>
            </div>
          </div>

          <div className="bg-white/[0.03] border border-white/10 rounded-2xl p-5 flex flex-col gap-1 justify-center">
            <Clock size={18} className="text-blue-400 mb-1" />
            <div className="text-2xl font-bold">{totalHours}h</div>
            <div className="text-xs text-muted-foreground">Tracked {statsRange.label}</div>
          </div>

          <div className="bg-white/[0.03] border border-white/10 rounded-2xl p-5 flex flex-col gap-1 justify-center">
            <BarChart2 size={18} className="text-purple-400 mb-1" />
            <div className="text-2xl font-bold">{desktop?.sessions.length ?? 0}</div>
            <div className="text-xs text-muted-foreground">Apps used</div>
          </div>

          <div className="bg-white/[0.03] border border-white/10 rounded-2xl p-5 flex flex-col gap-1 justify-center">
            <Zap size={18} className="text-yellow-400 mb-1" />
            <div className="text-2xl font-bold">{browser?.events_today ?? 0}</div>
            <div className="text-xs text-muted-foreground">Browser events · {statsRange.label}</div>
          </div>
        </div>

        <GoogleCalendarSyncPanel refreshKey={plannerRefresh} />

        <div className="w-full bg-white/[0.03] border border-white/10 rounded-2xl p-6 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="font-semibold flex items-center gap-2">
              <CalendarDays size={16} className="text-primary" />
              Planner calendar
            </h2>
            {adherence && (
              <span
                className="rounded-full border border-emerald-500/25 bg-emerald-500/10 px-2.5 py-1 text-xs text-emerald-200 tabular-nums"
                title="Effective focus for the selected day (planned ∩ productive)"
              >
                On-plan {(adherence.effective_focus_minutes / 60).toFixed(1)}h
                {adherence.planned_minutes > 0
                  ? ` · ${Math.round((adherence.adherence_pct ?? 0))}% plan`
                  : ""}
              </span>
            )}
          </div>

          <PlannerCalendar
            expanded
            refreshKey={plannerRefresh}
            selectedDay={plannerDay}
            onSelectedDayChange={setPlannerDay}
            view={calendarView}
            onViewChange={setCalendarView}
          />
        </div>

        <TodayPanel
          compact
          day={plannerDay}
          refreshKey={plannerRefresh}
          dueReviews={dueReviews}
          onPlannerChange={bumpPlanner}
        />

        <details className="group rounded-2xl border border-white/10 bg-white/[0.03] open:pb-4">
          <summary className="cursor-pointer list-none flex items-center gap-2 px-5 py-3.5 text-sm font-medium text-muted-foreground hover:text-foreground">
            <ChevronRight size={14} className="transition-transform group-open:rotate-90 text-primary" />
            Plan vs actual & insights
            <span className="text-[10px] font-normal opacity-70">day ribbon, streak, variance</span>
          </summary>
          <div className="px-5 space-y-6">
            <PlanVsActualDashboard
              selectedDay={plannerDay}
              onSelectedDayChange={setPlannerDay}
              refreshKey={plannerRefresh}
              trackerHealth={trackerHealth}
              adherenceDays={adherenceWindow}
              adherenceEnd={adherenceEnd}
              variancePreset={variancePreset}
            />

            <CalendarInfographics
              desktop={desktop}
              dueReviews={dueReviews}
              rangeLabel={statsRange.label}
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
          </div>
        </details>

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
      <div className="grid gap-4 xl:grid-cols-[minmax(18rem,22rem)_minmax(0,1fr)] items-start">
        {/* Left: steps */}
        <div className="space-y-3 min-w-0 xl:sticky xl:top-3 xl:max-h-[calc(100vh-6rem)] xl:overflow-y-auto xl:pr-1">
          <ol className="grid grid-cols-4 gap-1 text-[10px]">
            {(
              [
                { id: "goals" as const, n: 1, label: "Goals", done: goalsDone },
                { id: "routines" as const, n: 2, label: "Routines", done: routinesDone },
                { id: "propose" as const, n: 3, label: "Propose", done: proposeDone },
                { id: "done" as const, n: 4, label: "Apply", done: finishDone },
              ] as const
            ).map((s) => (
              <li key={s.id}>
                <button
                  type="button"
                  onClick={() => setPlanStep(s.id)}
                  className={`w-full rounded-lg border px-1.5 py-2 flex flex-col items-center gap-1 text-center transition-colors ${
                    planStep === s.id
                      ? "border-primary/50 bg-primary/15 text-foreground"
                      : s.done
                        ? "border-emerald-500/35 bg-emerald-500/10 text-emerald-100"
                        : "border-white/10 bg-white/[0.03] text-muted-foreground hover:bg-white/[0.05]"
                  }`}
                >
                  <span
                    className={`h-5 w-5 rounded-full text-[10px] font-semibold flex items-center justify-center ${
                      s.done ? "bg-emerald-500/80 text-white" : planStep === s.id ? "bg-primary/80 text-primary-foreground" : "bg-white/10"
                    }`}
                  >
                    {s.done ? <CheckCircle2 size={11} /> : s.n}
                  </span>
                  {s.label}
                </button>
              </li>
            ))}
          </ol>

          {planStep === "goals" && (
            <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 space-y-3">
              <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">1 · Goals</h2>
              <ProductivityGoalsPanel
                adherence={adherence}
                onGoalsTextChange={(text) => setProposeGoals(text)}
              />
              <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
                <Link to="/journal" className="text-xs text-primary hover:underline inline-flex items-center gap-1">
                  <PenLine size={12} /> Journal
                </Link>
                <button
                  type="button"
                  disabled={!goalsDone}
                  onClick={() => setPlanStep("routines")}
                  className="rounded-lg bg-primary px-3 py-1.5 text-xs text-primary-foreground hover:bg-primary/90 disabled:opacity-40"
                >
                  Next · Routines
                </button>
              </div>
            </div>
          )}

          {planStep === "routines" && (
            <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 space-y-3">
              <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">2 · Routines</h2>
              <p className="text-xs text-muted-foreground">
                Lock daily rhythm, then build the week.
              </p>
              <div className="space-y-4">
                <div className="rounded-xl border border-white/10 bg-black/20 p-4">
                  <RoutinesPanel onApplied={bumpPlanner} onRoutinesChange={onRoutinesChange} />
                </div>
                <div className="rounded-xl border border-white/10 bg-black/20 p-4">
                  <TimetablePanel
                    onPlannerUpdated={() => {
                      bumpPlanner();
                      setHasTimetableBlocks(true);
                    }}
                  />
                </div>
              </div>
              <div className="flex flex-wrap justify-between gap-2 pt-1">
                <button
                  type="button"
                  onClick={() => setPlanStep("goals")}
                  className="rounded-lg border border-white/10 px-3 py-1.5 text-xs hover:bg-white/5"
                >
                  Back
                </button>
                <button
                  type="button"
                  onClick={() => setPlanStep("propose")}
                  className="rounded-lg bg-primary px-3 py-1.5 text-xs text-primary-foreground hover:bg-primary/90"
                >
                  Next · Propose
                </button>
              </div>
            </div>
          )}

          {(planStep === "propose" || planStep === "done") && (
            <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 space-y-4">
              <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                {planStep === "done" ? "4 · Applied" : "3 · Propose"}
              </h2>

              {planStep === "done" ? (
                <div className="space-y-3">
                  <p className="text-sm text-emerald-200">
                    Plan written to the calendar on the right.
                  </p>
                  {exportHint ? (
                    <p className="text-xs text-sky-300 truncate" title={exportHint}>{exportHint}</p>
                  ) : null}
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={() => setPlanStep("propose")}
                      className="rounded-lg border border-white/10 px-3 py-1.5 text-xs hover:bg-white/5"
                    >
                      Propose again
                    </button>
                    <button
                      type="button"
                      onClick={() => setTab("calendar")}
                      className="rounded-lg bg-primary px-3 py-1.5 text-xs text-primary-foreground hover:bg-primary/90"
                    >
                      Open Calendar tab
                    </button>
                  </div>
                </div>
              ) : (
                <>
                  <p className="text-xs text-muted-foreground">
                    Smart fill uses goals + free gaps. Drafts appear dashed on the calendar.
                  </p>
                  <div className="space-y-3 rounded-xl border border-white/10 bg-black/20 p-3">
                    <div className="space-y-1.5">
                      <span className="text-[10px] text-muted-foreground">Horizon</span>
                      <div className="grid grid-cols-2 gap-1.5">
                        {(
                          [
                            ["day", "Today"],
                            ["week", "7 days"],
                            ["month", "30 days"],
                            ["custom", "Custom"],
                          ] as const
                        ).map(([id, label]) => (
                          <button
                            key={id}
                            type="button"
                            onClick={() => setProposeHorizon(id)}
                            className={`rounded-lg px-2 py-1.5 text-[11px] border transition-colors ${
                              proposeHorizon === id
                                ? "border-primary/50 bg-primary/20 text-foreground"
                                : "border-white/10 bg-black/30 text-muted-foreground hover:bg-white/5"
                            }`}
                          >
                            {label}
                          </button>
                        ))}
                      </div>
                      {proposeHorizon === "custom" && (
                        <div className="flex items-center gap-2 text-xs">
                          <span className="text-muted-foreground">Days</span>
                          <input
                            type="number"
                            min={1}
                            max={62}
                            value={customHorizonDays}
                            onChange={(e) =>
                              setCustomHorizonDays(Math.max(1, Math.min(62, Number(e.target.value) || 14)))
                            }
                            className="w-14 rounded border border-white/10 bg-black/40 px-2 py-1 text-foreground"
                          />
                        </div>
                      )}
                    </div>
                    <label className="flex items-center gap-2 text-[11px] text-muted-foreground">
                      Look-back
                      <input
                        type="number"
                        min={1}
                        max={31}
                        value={exportDays}
                        onChange={(e) => setExportDays(Math.max(1, Math.min(31, Number(e.target.value) || 7)))}
                        className="w-12 rounded border border-white/10 bg-black/40 px-1.5 py-1 text-foreground"
                      />
                      days
                    </label>
                    <button
                      type="button"
                      disabled={proposing}
                      onClick={() => void runPropose("smart")}
                      className="w-full flex items-center justify-center gap-1.5 rounded-lg bg-primary px-3 py-2 text-sm text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                    >
                      {proposing ? <Loader2 size={14} className="animate-spin" /> : <CalendarDays size={14} />}
                      Build smart
                    </button>
                    <button
                      type="button"
                      disabled={proposing || !proposed?.length}
                      onClick={() => void runPropose("review")}
                      className="w-full rounded-lg border border-primary/40 bg-primary/10 px-3 py-1.5 text-xs hover:bg-primary/20 disabled:opacity-50"
                    >
                      AI review draft
                    </button>
                    <button
                      type="button"
                      disabled={proposing}
                      onClick={() => void runPropose("full")}
                      className="w-full rounded-lg border border-white/15 bg-white/5 px-3 py-1.5 text-xs text-muted-foreground hover:bg-white/10 disabled:opacity-50"
                    >
                      AI from scratch
                    </button>
                    {exportHint ? (
                      <p className="text-[10px] text-sky-300 truncate" title={exportHint}>{exportHint}</p>
                    ) : null}
                  </div>

                  {(proposed || proposeMeta) && (
                    <ProposePlanPreview
                      embedded
                      blocks={proposed || []}
                      rationale={proposeMeta?.rationale}
                      usedLlm={proposeMeta?.used_llm}
                      proposing={proposing}
                      goalsText={proposeGoals}
                      scaledDailyHours={proposeMeta?.scaled_daily_hours}
                      onChange={setProposed}
                      onApply={(range) => void applyPropose(range)}
                      onDismiss={() => {
                        setProposed(null);
                        setProposeMeta(null);
                      }}
                    />
                  )}
                </>
              )}
            </div>
          )}
        </div>

        {/* Right: live calendar (Plan only) */}
        <div className="min-w-0 rounded-2xl border border-white/10 bg-white/[0.03] p-4 space-y-3 xl:sticky xl:top-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="font-semibold text-sm flex items-center gap-2">
              <CalendarDays size={15} className="text-primary" />
              Live calendar
              {proposed?.length ? (
                <span className="rounded-md border border-primary/35 bg-primary/10 px-1.5 py-0.5 text-[10px] font-normal text-primary">
                  {proposed.filter((b) => b.source !== "existing").length} drafts
                </span>
              ) : null}
            </h2>
            <span className="text-[10px] text-muted-foreground">Dashed = not applied yet</span>
          </div>
          <PlannerCalendar
            expanded
            refreshKey={plannerRefresh}
            selectedDay={plannerDay}
            onSelectedDayChange={setPlannerDay}
            view={calendarView}
            onViewChange={setCalendarView}
            draftBlocks={proposed}
          />
        </div>
      </div>
      )}

      {tab === "settings" && (
      <div className="space-y-8">
        <div className="rounded-xl border border-border/50 bg-background/35 px-4 py-3 text-sm text-muted-foreground">
          Tracker scoring, wearables, reminders, and exports.
        </div>

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
