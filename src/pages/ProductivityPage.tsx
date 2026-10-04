import { useState, useEffect, useCallback, useMemo, useRef, lazy, Suspense, type ReactNode } from "react";
import {
  Monitor, Globe, CheckCircle2,
  Terminal, Code2, BookOpen, PenLine,
  Gamepad2, Music, MessageSquare, FileText, Folder, Cpu,
  ChevronDown, ChevronRight, Download, Loader2,
} from "lucide-react";
import { Views, type View } from "react-big-calendar";
import { fetchDesktopStats, fetchBrowserStats, fetchTrackerHealth, fetchDesktopTimeline, clearDemoClock, fetchDemoClock, fetchGoalsStatus } from "../api/behaviorClient";
import type { DesktopStats, BrowserStats, AppSession, BrowserSite, BrowserDomain, TrackerHealth, DesktopTimeline, DemoClockStatus, GoalsStatusResponse } from "../api/behaviorClient";
import {
  dayRollupToDesktopStats,
  dayRollupToGoalsStatus,
  emptyDesktopStats,
  fetchDayRollupMirror,
} from "../api/focusMirrors";
import { isFocusDesktopShell } from "../utils/focusDesktopShell";
import { useFocusStatus } from "../hooks/useFocusStatus";
import { GlanceBar } from "../components/productivity/GlanceBar";
import HomeModeBoard from "../components/productivity/HomeModeBoard";
import DayLoopLanding from "../components/productivity/DayLoopLanding";
import BedtimeOverlay from "../components/productivity/BedtimeOverlay";
import MorningBibleOverlay from "../components/productivity/MorningBibleOverlay";
import MorningPlanOverlay from "../components/productivity/MorningPlanOverlay";
import { PlanVsActualDashboard } from "../components/productivity/PlanVsActualDashboard";
import { ConfirmPlanButton } from "../components/productivity/ConfirmPlanButton";
import { TimetablePanel } from "../components/productivity/TimetablePanel";
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "../app/components/ui/resizable";
import {
  ProductivitySettingsTab,
  parseSettingsSection,
  type SettingsSectionId,
} from "../components/productivity/ProductivitySettingsTab";
import { RoutinesPanel } from "../components/productivity/RoutinesPanel";
import { ProposeStepPanel, applyRangeForHorizon } from "../components/productivity/ProposeStepPanel";
import { proposeBlockStatKind, blockDurationMinutes } from "../components/productivity/proposeBlockStats";
import { Link, useSearchParams } from "react-router";
import {
  fetchAdherence,
  createPlannerBlock,
  downloadProductivityWeekExport,
  MAX_PRODUCTIVITY_EXPORT_DAYS,
  proposeWeekFromExport,
  mergeProposeResult,
  applyProposedBlocks,
  fetchPlanDrift,
  fetchPlannerBlocks,
  syncPlannerToGoogleCalendar,
  type AdherenceSummary,
  type PlanDriftSummary,
  type ProposedPlannerBlock,
  type PlannerRoutine,
} from "../api/plannerClient";
import { fetchDueReview } from "../api/globalQuizClient";
import { fetchHubDaily } from "../api/hubClient";
import ShutdownRitualPanel from "../components/productivity/ShutdownRitualPanel";
import WeeklyDigestPanel from "../components/productivity/WeeklyDigestPanel";
import ProductivityGoalsPanel, {
  formatGoalsForPrompt,
  GOALS_UPDATED_EVENT,
  loadProductivityGoals,
} from "../components/productivity/ProductivityGoalsPanel";
import GoogleCalendarSyncPanel from "../components/productivity/GoogleCalendarSyncPanel";
import PlannerRemindersPanel from "../components/productivity/PlannerRemindersPanel";
import {
  statsRangeForView,
  type CalendarStatsView,
} from "../components/productivity/planVsActualUtils";
import { studyMinutesFromBlocks } from "../components/productivity/fillFocusStudyGaps";
import { endOfDay, startOfDay } from "date-fns";
import { formatHoursMinsFromSeconds } from "../utils/formatDuration";

const PlannerCalendar = lazy(() =>
  import("../components/productivity/PlannerCalendar").then((m) => ({ default: m.PlannerCalendar })),
);

// ── Helpers ──────────────────────────────────────────────────────────────────

function fmtSeconds(s: number): string {
  return formatHoursMinsFromSeconds(s);
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

function parseApiDay(iso: string): Date {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, (m || 1) - 1, d || 1);
}

function addApiDays(iso: string, delta: number): string {
  const d = parseApiDay(iso);
  d.setDate(d.getDate() + delta);
  return toApiDay(d);
}

/** Inclusive day count between YYYY-MM-DD bounds (local calendar). */
function inclusiveExportDays(startIso: string, endIso: string): number {
  const ms = parseApiDay(endIso).getTime() - parseApiDay(startIso).getTime();
  return Math.floor(ms / 86_400_000) + 1;
}

function clampExportWindow(
  startIso: string,
  endIso: string,
): { start: string; end: string; days: number; clamped: boolean } {
  let start = startIso;
  let end = endIso;
  if (parseApiDay(start).getTime() > parseApiDay(end).getTime()) {
    [start, end] = [end, start];
  }
  let days = inclusiveExportDays(start, end);
  let clamped = false;
  if (days < 1) {
    days = 1;
    start = end;
    clamped = true;
  } else if (days > MAX_PRODUCTIVITY_EXPORT_DAYS) {
    start = addApiDays(end, -(MAX_PRODUCTIVITY_EXPORT_DAYS - 1));
    days = MAX_PRODUCTIVITY_EXPORT_DAYS;
    clamped = true;
  }
  return { start, end, days, clamped };
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
        <span className="text-sm font-medium truncate" title={session.exe}>
          {session.display_name || session.exe}
        </span>
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
  const focusShell = isFocusDesktopShell();
  const focusStatus = useFocusStatus();
  const [desktop, setDesktop] = useState<DesktopStats | null>(null);
  const [browser, setBrowser] = useState<BrowserStats | null>(null);
  const [trackerHealth, setTrackerHealth] = useState<TrackerHealth | null>(null);
  const [timeline, setTimeline] = useState<DesktopTimeline | null>(null);
  const [loading, setLoading] = useState(true);
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date());
  const [adherence, setAdherence] = useState<AdherenceSummary | null>(null);
  const [dueReviews, setDueReviews] = useState(0);
  const [sleepHours, setSleepHours] = useState<number | null>(null);
  const [sleepScore, setSleepScore] = useState<number | null>(null);
  const [goalsStatus, setGoalsStatus] = useState<GoalsStatusResponse | null>(null);
  const [plannerDay, setPlannerDay] = useState(() => {
    const raw = new URLSearchParams(window.location.search).get("day");
    if (raw && /^\d{4}-\d{2}-\d{2}$/.test(raw)) {
      const [y, m, d] = raw.split("-").map(Number);
      return new Date(y, m - 1, d, 12, 0, 0, 0);
    }
    return new Date();
  });
  const [calendarView, setCalendarView] = useState<View>(Views.DAY);
  const [calendarVisited, setCalendarVisited] = useState(false);
  const [searchParams, setSearchParams] = useSearchParams();
  const [demoClock, setDemoClock] = useState<DemoClockStatus | null>(null);
  const rawTab = searchParams.get("tab");
  /** Sidebar owns nav: Home | Calendar | Planner | Analytics | Settings (+ Bible route). */
  const tab: "home" | "calendar" | "plan" | "analytics" | "settings" =
    rawTab === "calendar" ||
    rawTab === "plan" ||
    rawTab === "analytics" ||
    rawTab === "settings"
      ? rawTab
      : "home";
  const settingsSection = parseSettingsSection(searchParams.get("section"));
  const setSettingsSection = useCallback(
    (id: SettingsSectionId) => {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          next.set("tab", "settings");
          next.set("section", id);
          return next;
        },
        { replace: true },
      );
    },
    [setSearchParams],
  );
  useEffect(() => {
    if (tab === "calendar") setCalendarVisited(true);
  }, [tab]);

  const setTab = useCallback(
    (id: "home" | "calendar" | "plan" | "analytics" | "settings") => {
      if (id === "calendar" || id === "home") {
        setPlannerDay(startOfDay(new Date()));
        setCalendarView(Views.DAY);
      }
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          next.set("tab", id);
          if (id !== "settings") next.delete("section");
          if (id === "home") next.delete("day");
          return next;
        },
        { replace: true },
      );
    },
    [setSearchParams],
  );
  const [plannerRefresh, setPlannerRefresh] = useState(0);
  const [exporting, setExporting] = useState(false);
  const [exportHint, setExportHint] = useState<string | null>(null);
  const [exportDays, setExportDays] = useState(7);
  /** Draft for the days number input so typing "107" is not snapped mid-edit. */
  const [exportDaysText, setExportDaysText] = useState("7");
  const [exportEndDay, setExportEndDay] = useState(() => toApiDay(new Date()));
  const [exportStartDay, setExportStartDay] = useState(() =>
    addApiDays(toApiDay(new Date()), -6),
  );
  const [exportRangeNote, setExportRangeNote] = useState<string | null>(null);
  /** When false (default), API skip_empty=true — omit blank calendar days. */
  const [exportIncludeEmpty, setExportIncludeEmpty] = useState(false);
  const [exportInclude, setExportInclude] = useState({
    summary: true,
    patterns: true,
    by_day: true,
    blocks: true,
    hints: true,
    policy: true,
    wearable: true,
    tables: true,
    sessions: true,
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
  const [planDrift, setPlanDrift] = useState<PlanDriftSummary | null>(null);

  const onRoutinesChange = useCallback((rows: PlannerRoutine[]) => {
    setHasRoutines(rows.length > 0);
  }, []);

  const goalsDone = goalsConfirmed;
  const routinesDone = hasRoutines || hasTimetableBlocks;
  const proposeDone = Boolean(proposed?.length) || planAppliedThisSession;
  const finishDone = planAppliedThisSession;
  const syncDone = planAppliedThisSession; // last step available after apply
  const planStepRef = useRef<HTMLDivElement>(null);

  // Focus shell: never land on Study-only propose/sync steps
  useEffect(() => {
    if (!focusShell) return;
    if (planStep === "propose" || planStep === "sync") {
      setPlanStep("done");
    }
  }, [focusShell, planStep]);

  useEffect(() => {
    planStepRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [planStep]);

  useEffect(() => {
    const onGoals = () => setProposeGoals(formatGoalsForPrompt(loadProductivityGoals()));
    window.addEventListener(GOALS_UPDATED_EVENT, onGoals);
    return () => window.removeEventListener(GOALS_UPDATED_EVENT, onGoals);
  }, []);

  const plannerDayKey = useMemo(() => toApiDay(plannerDay), [plannerDay]);

  useEffect(() => {
    let cancelled = false;
    void fetchPlanDrift(plannerDayKey)
      .then((d) => {
        if (!cancelled) setPlanDrift(d);
      })
      .catch(() => {
        if (!cancelled) setPlanDrift(null);
      });
    return () => {
      cancelled = true;
    };
  }, [plannerDayKey, plannerRefresh, lastRefresh]);

  useEffect(() => {
    if (focusShell) {
      setDemoClock(null);
      return;
    }
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
  }, [plannerRefresh, lastRefresh, focusShell]);

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
        // Hero "planned" = study/work toward focus goal (not routines/free).
        setDayLockedHours(studyMinutesFromBlocks(rows) / 60);
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

  const loadAdherence = useCallback(async (day: Date) => {
    try {
      const a = await fetchAdherence(day);
      setAdherence(a);
    } catch {
      setAdherence(null);
    }
  }, []);

  const loadDue = useCallback(async () => {
    if (focusShell) {
      setDueReviews(0);
      return;
    }
    try {
      const d = await fetchDueReview(5);
      setDueReviews(d.count ?? d.items?.length ?? 0);
    } catch {
      setDueReviews(0);
    }
  }, [focusShell]);

  const bumpPlanner = useCallback(() => {
    setPlannerRefresh((k) => k + 1);
    void loadAdherence(plannerDay);
    void loadDue();
  }, [plannerDay, loadAdherence, loadDue]);

  useEffect(() => {
    if (focusShell) {
      setSleepHours(null);
      setSleepScore(null);
      return;
    }
    const day = toApiDay(plannerDay);
    void fetchHubDaily(day)
      .then((h) => {
        if (h && (h.sleep_minutes || 0) > 0) setSleepHours(h.sleep_minutes / 60);
        else setSleepHours(null);
        setSleepScore(h?.sleep_score && h.sleep_score > 0 ? h.sleep_score : null);
      })
      .catch(() => {
        setSleepHours(null);
        setSleepScore(null);
      });
  }, [plannerDay, plannerRefresh, focusShell]);

  useEffect(() => {
    if (focusShell) {
      // Focus: SoftLand goals come from status bus / rollup — never Study :8000.
      void fetchDayRollupMirror().then((rollup) => {
        setGoalsStatus(dayRollupToGoalsStatus(rollup));
      });
      return;
    }
    const day = toApiDay(plannerDay);
    void fetchGoalsStatus(day)
      .then(setGoalsStatus)
      .catch(() => setGoalsStatus(null));
  }, [plannerDay, plannerRefresh, focusShell]);

  // Keep GlanceBar / Home tracked minutes in sync with native rollup (DB → day_rollup.json).
  useEffect(() => {
    if (!focusShell || !focusStatus.dayRollup) return;
    setDesktop(dayRollupToDesktopStats(focusStatus.dayRollup));
    setGoalsStatus((prev) => dayRollupToGoalsStatus(focusStatus.dayRollup) ?? prev);
  }, [focusShell, focusStatus.updatedAt, focusStatus.dayRollup]);

  /** Header + GlanceBar — follow selected month/week/day. */
  const loadCore = useCallback(async () => {
    if (isFocusDesktopShell()) {
      // Enforcer mirrors only — no Study :8000 desktop-stats.
      const rollup = await fetchDayRollupMirror();
      if (rollup) {
        setDesktop(dayRollupToDesktopStats(rollup));
      } else {
        setDesktop(emptyDesktopStats(toApiDay(statsRange.from)));
      }
      setTrackerHealth({
        tracker_alive: Boolean(rollup),
        status: rollup ? "running" : "no_data",
        last_event_at: null,
        sessions_today: rollup?.session_count ?? 0,
        total_seconds_today: Math.round((rollup?.productive_minutes ?? 0) * 60),
        source: "day_rollup",
        hint: rollup ? "Native day rollup" : "Waiting for enforcer rollup",
      });
      return;
    }
    const results = await Promise.allSettled([
      fetchDesktopStatsForRange(statsRange.from, statsRange.to),
      fetchTrackerHealth(),
    ]);
    if (results[0].status === "fulfilled") setDesktop(results[0].value);
    if (results[1].status === "fulfilled") setTrackerHealth(results[1].value);
  }, [statsRange.from.getTime(), statsRange.to.getTime()]);

  /** Screen-time extras — KPIs detail + timeline for the focused day. */
  const loadScreenTime = useCallback(async () => {
    const timelineDay = toApiDay(plannerDay);
    if (isFocusDesktopShell()) {
      setBrowser({
        connected: false,
        events_today: 0,
        total_events: 0,
        top_category: "",
        avg_productivity_score: 0,
        top_domains: [],
        recent_sites: [],
        category_breakdown: {},
        date: timelineDay,
        source: "offline",
      });
      setTimeline(null);
      return;
    }
    const results = await Promise.allSettled([
      fetchBrowserStatsForRange(statsRange.from, statsRange.to),
      fetchDesktopTimeline(timelineDay),
    ]);
    if (results[0].status === "fulfilled") setBrowser(results[0].value);
    if (results[1].status === "fulfilled") setTimeline(results[1].value);
  }, [plannerDay.getTime(), statsRange.from.getTime(), statsRange.to.getTime()]);

  /** Full refresh (Sync / Refresh button) — core + screen-time extras. */
  const load = useCallback(async () => {
    setLoading(true);
    // Partial failures are silent — keep last good data; no amber "Failed to fetch" banners.
    await loadCore();
    await loadScreenTime();
    setLastRefresh(new Date());
    setLoading(false);
  }, [loadCore, loadScreenTime]);

  const applyExportWindow = useCallback(
    (startIso: string, endIso: string, note?: string | null) => {
      const next = clampExportWindow(startIso, endIso);
      setExportStartDay(next.start);
      setExportEndDay(next.end);
      setExportDays(next.days);
      setExportDaysText(String(next.days));
      if (note !== undefined) setExportRangeNote(note);
      else if (next.clamped) {
        setExportRangeNote(
          `Range clamped to ${MAX_PRODUCTIVITY_EXPORT_DAYS} days (API max).`,
        );
      } else {
        setExportRangeNote(null);
      }
    },
    [],
  );

  const setExportDaysWindow = useCallback(
    (days: number, endIso?: string) => {
      const end = endIso ?? exportEndDay;
      const safe = Math.max(1, Math.min(MAX_PRODUCTIVITY_EXPORT_DAYS, Math.floor(days) || 1));
      const start = addApiDays(end, -(safe - 1));
      const note =
        safe !== Math.floor(days)
          ? `Days clamped to ${safe} (allowed 1–${MAX_PRODUCTIVITY_EXPORT_DAYS}).`
          : null;
      applyExportWindow(start, end, note);
    },
    [applyExportWindow, exportEndDay],
  );

  const exportWeek = useCallback(async (format: "json" | "csv" | "csv_wide") => {
    setExporting(true);
    setExportHint(null);
    try {
      const include = Object.entries(exportInclude)
        .filter(([, on]) => on)
        .map(([k]) => k)
        .join(",");
      const skipEmpty = !exportIncludeEmpty;
      const days = Math.max(
        1,
        Math.min(MAX_PRODUCTIVITY_EXPORT_DAYS, Math.floor(exportDays) || 1),
      );
      if (days !== exportDays) {
        setExportDaysWindow(days);
      }
      await downloadProductivityWeekExport(days, format, {
        include: include || "summary,patterns,policy",
        productiveOnly: exportProductiveOnly,
        skipEmpty,
        endDay: exportEndDay,
      });
      const emptyNote = skipEmpty ? " · empty days omitted" : " · empty days included";
      const rangeLabel =
        exportStartDay === addApiDays(exportEndDay, -(days - 1))
          ? `${exportStartDay} → ${exportEndDay}`
          : `${days}d ending ${exportEndDay}`;
      setExportHint(`Downloaded ${rangeLabel} ${format.toUpperCase()}${emptyNote}`);
    } catch (e: unknown) {
      setExportHint(e instanceof Error ? e.message : "Export failed");
    } finally {
      setExporting(false);
    }
  }, [
    exportDays,
    exportEndDay,
    exportStartDay,
    exportInclude,
    exportIncludeEmpty,
    exportProductiveOnly,
    setExportDaysWindow,
  ]);

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

        const mergedRes = await mergeProposeResult({
          api_blocks: (res.blocks || []).map((b) => ({
            ...b,
            source: (b.source ?? "study") as ProposedPlannerBlock["source"],
          })),
          range_start: proposeRangeStart,
          horizon_days: horizonDays,
        });
        const merged = mergedRes.blocks;

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

  // Initial + polling: do NOT re-fetch on every tab switch (that made Settings feel slow).
  useEffect(() => {
    let cancelled = false;
    const tick = async (showSpinner: boolean) => {
      if (typeof document !== "undefined" && document.visibilityState === "hidden") return;
      if (showSpinner) setLoading(true);
      await loadCore();
      await loadScreenTime();
      if (cancelled) return;
      setLastRefresh(new Date());
      if (showSpinner) setLoading(false);
    };
    void tick(true);
    const id = setInterval(() => {
      void tick(false);
    }, 60_000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [loadCore, loadScreenTime]);

  // Soft refresh on tab enter — Focus shell skips (mirrors + status bus already tick).
  useEffect(() => {
    if (focusShell) return;
    if (tab !== "home" && tab !== "calendar" && tab !== "settings") return;
    void loadScreenTime();
  }, [tab, loadScreenTime, focusShell]);

  useEffect(() => {
    // Focus: defer adherence so day.loop_snapshot isn't stuck behind plan.adherence on cold start.
    if (focusShell) {
      const id = window.setTimeout(() => void loadAdherence(plannerDay), 2500);
      return () => window.clearTimeout(id);
    }
    void loadAdherence(plannerDay);
  }, [plannerDay, loadAdherence, focusShell]);

  const trackerStatus = trackerHealth?.status ?? (desktop?.tracker_running ? "running" : "no_data");
  const maxSec = desktop?.sessions[0]?.seconds ?? 1;
  const totalHours = desktop ? (desktop.total_seconds / 3600).toFixed(1) : "—";
  const avgScore = desktop?.avg_productivity_score ?? 0;

  return (
    <>
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

      {tab === "home" && (
      <div className="space-y-6">
        {focusShell ? (
          <HomeModeBoard
            day={plannerDay}
            refreshKey={plannerRefresh}
            desktop={desktop}
            dueReviews={dueReviews}
            rangeLabel={statsRange.label}
            sleepHours={sleepHours}
            sleepScore={sleepScore}
            goalsStatus={goalsStatus}
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
        ) : (
          <>
            <DayLoopLanding />
            <GlanceBar
              desktop={desktop}
              dueReviews={dueReviews}
              rangeLabel={statsRange.label}
              sleepHours={sleepHours}
              sleepScore={sleepScore}
              goalsStatus={goalsStatus}
            />
          </>
        )}
        {planDrift && planDrift.block_count > 0 ? (
          <div className="rounded-xl border border-white/10 bg-white/[0.03] px-4 py-3 space-y-1">
            <p className="text-xs font-medium text-foreground">Plan vs actual</p>
            <p className="text-[11px] text-muted-foreground">{planDrift.summary}</p>
            {planDrift.lines.length > 0 ? (
              <ul className="text-[11px] text-amber-100/90 space-y-0.5 list-disc list-inside">
                {planDrift.lines.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            ) : (
              <p className="text-[11px] text-emerald-200/80">On track so far today.</p>
            )}
          </div>
        ) : null}
        {!focusShell ? (
          <ShutdownRitualPanel
            day={plannerDay}
            desktop={desktop}
            adherence={adherence}
            goalsStatus={goalsStatus}
            refreshKey={plannerRefresh}
            onComplete={() => bumpPlanner()}
          />
        ) : null}
      </div>
      )}

      {(tab === "calendar" || calendarVisited) && (
      <div className={tab === "calendar" ? "space-y-6" : "hidden"} aria-hidden={tab !== "calendar"}>
        <div className="w-full">
          <Suspense fallback={<p className="text-sm text-muted-foreground px-2 py-6">Opening calendar…</p>}>
          <PlannerCalendar
            expanded
            refreshKey={plannerRefresh}
            selectedDay={plannerDay}
            onSelectedDayChange={setPlannerDay}
            view={calendarView}
            onViewChange={setCalendarView}
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
          </Suspense>
        </div>
      </div>
      )}

      {tab === "analytics" && (
      <div className="space-y-6">
        <div className="space-y-5 rounded-2xl border border-white/10 bg-white/[0.03] p-5 sm:p-6 gloss-panel">
          <PlanVsActualDashboard
            selectedDay={plannerDay}
            onSelectedDayChange={setPlannerDay}
            refreshKey={plannerRefresh}
            trackerHealth={focusShell ? null : trackerHealth}
            adherenceDays={adherenceWindow}
            adherenceEnd={adherenceEnd}
            analyticsFrom={statsRange.from}
            analyticsTo={statsRange.to}
            analyticsView={statsView}
            onNavigateTab={setTab}
          />
        </div>

        {!focusShell ? (
        <details className="group rounded-2xl border border-white/10 bg-white/[0.03] open:pb-4" open>
          <summary className="cursor-pointer list-none flex items-center gap-2 px-5 py-3.5 text-sm font-medium text-muted-foreground hover:text-foreground">
            <ChevronRight size={14} className="transition-transform group-open:rotate-90 text-primary" />
            Weekly digest
          </summary>
          <div className="px-5 pb-2">
            <WeeklyDigestPanel endDay={toApiDay(plannerDay)} refreshKey={plannerRefresh} />
          </div>
        </details>
        ) : null}

        <details className="group rounded-2xl border border-white/10 bg-white/[0.03] open:pb-4" open={!focusShell}>
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
                <div className="text-center py-6 text-muted-foreground text-sm space-y-2">
                  <Monitor size={24} className="mx-auto opacity-30" />
                  <p>
                    {focusShell
                      ? "No desktop sessions in this range yet — productive minutes still show above when day rollup is available."
                      : "No desktop data yet."}
                  </p>
                  {!focusShell ? (
                    <code className="block bg-black/40 px-3 py-1.5 rounded-lg text-xs font-mono mx-auto w-fit">
                      scripts\install_tracker_startup.bat
                    </code>
                  ) : (
                    <button
                      type="button"
                      onClick={() => setTab("settings")}
                      className="text-xs text-primary hover:underline underline-offset-2"
                    >
                      Open Settings
                    </button>
                  )}
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
      <ResizablePanelGroup
        direction="horizontal"
        autoSaveId="calt-plan-calendar-split"
        className="min-h-[min(70vh,calc(100vh-5.5rem))] gap-0 rounded-2xl"
      >
        {/* Left: planning steps */}
        <ResizablePanel defaultSize={44} minSize={28} className="min-w-0">
        <div className="flex h-full min-w-0 flex-col gap-3.5 pr-2 xl:max-h-[calc(100vh-5.5rem)] xl:overflow-y-auto">
          <nav aria-label="Plan steps" className="shrink-0">
            <ol
              className={`plan-step-rail ${
                focusShell ? "plan-step-rail--3" : "plan-step-rail--5"
              }`}
            >
              {(
                focusShell
                  ? ([
                      { id: "routines" as const, label: "Routines", done: routinesDone },
                      { id: "goals" as const, label: "Goals", done: goalsDone },
                      { id: "done" as const, label: "Ready", done: finishDone || goalsDone },
                    ] as const)
                  : ([
                      { id: "routines" as const, label: "Routines", done: routinesDone },
                      { id: "goals" as const, label: "Goals", done: goalsDone },
                      { id: "propose" as const, label: "Build", done: proposeDone },
                      { id: "done" as const, label: "Apply", done: finishDone },
                      { id: "sync" as const, label: "Watch", done: syncDone && planStep === "sync" },
                    ] as const)
              ).map((s) => {
                const active = planStep === s.id;
                return (
                  <li key={s.id} className="min-w-0">
                    <button
                      type="button"
                      onClick={() => setPlanStep(s.id)}
                      aria-current={active ? "step" : undefined}
                      className={`plan-step-rail__btn ${active ? "is-active" : ""} ${
                        s.done && !active ? "is-done" : ""
                      }`}
                    >
                      {s.done && !active ? (
                        <CheckCircle2 size={12} className="plan-step-rail__check" aria-hidden />
                      ) : null}
                      <span className="plan-step-rail__label">{s.label}</span>
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
          {(() => {
            const stepActions = (
              <div className="space-y-2 border-t border-white/10 pt-3">
                <ConfirmPlanButton size="block" />
                <div className="flex flex-wrap items-center justify-between gap-2">
                  {planStep === "routines" ? (
                    <>
                      <span className="text-[11px] text-muted-foreground">
                        Lock times, then set focus hours
                      </span>
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
                        <Link
                          to="/journal"
                          className="text-xs text-primary hover:underline inline-flex items-center gap-1"
                        >
                          <PenLine size={12} /> Journal
                        </Link>
                        <button
                          type="button"
                          onClick={() => {
                            setGoalsConfirmed(true);
                            setPlanStep(focusShell ? "done" : "propose");
                          }}
                          className="rounded-xl bg-primary px-4 py-2 text-xs font-medium text-primary-foreground hover:bg-primary/90"
                        >
                          {focusShell ? "Next · Ready" : "Next · Build"}
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
                        <span className="text-[11px] text-muted-foreground">
                          Generate a schedule to continue
                        </span>
                      )}
                    </>
                  ) : planStep === "done" ? (
                    <>
                      <button
                        type="button"
                        onClick={() => setPlanStep(focusShell ? "goals" : "propose")}
                        className="rounded-xl border border-white/10 px-4 py-2 text-xs hover:bg-white/5"
                      >
                        Back
                      </button>
                      {!focusShell ? (
                        <button
                          type="button"
                          onClick={() => setPlanStep("sync")}
                          className="rounded-xl bg-primary px-4 py-2 text-xs font-medium text-primary-foreground hover:bg-primary/90"
                        >
                          Next · Watch
                        </button>
                      ) : (
                        <button
                          type="button"
                          onClick={() => setTab("calendar")}
                          className="rounded-xl bg-primary px-4 py-2 text-xs font-medium text-primary-foreground hover:bg-primary/90"
                        >
                          Open Calendar
                        </button>
                      )}
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
            );

            return (
              <>
          {planStep === "routines" && (
            <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 space-y-4">
              <div>
                <h2 className="text-sm font-semibold text-foreground">1 · Routines</h2>
                <p className="text-xs text-muted-foreground mt-1">
                  Lock fixed times first (meals, workout, devotion) and set sleep / wake. The day list on the
                  right updates as you apply.
                </p>
              </div>
              <div className="space-y-4">
                <div className="rounded-xl border border-white/10 bg-black/20 p-4">
                  <RoutinesPanel onApplied={bumpPlanner} onRoutinesChange={onRoutinesChange} />
                </div>
                {!focusShell ? (
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
                ) : null}
              </div>
              {stepActions}
            </div>
          )}

          {planStep === "goals" && (
            <ProductivityGoalsPanel
              adherence={adherence}
              lockedHours={dayLockedHours}
              sleepScore={sleepScore}
              planRefreshKey={plannerRefresh}
              onPlanBlocksChange={bumpPlanner}
              onOpenCalendar={() => setTab("calendar")}
              onGoalsTextChange={(text) => setProposeGoals(text)}
              onConfirmed={() => setGoalsConfirmed(true)}
              footer={stepActions}
            />
          )}

          {planStep === "propose" && !focusShell && (
            <div className="space-y-3">
              <ProposeStepPanel
                horizon={proposeHorizon}
                onHorizonChange={setProposeHorizon}
                customHorizonDays={customHorizonDays}
                onCustomHorizonDaysChange={setCustomHorizonDays}
                horizonDays={horizonDays}
                rangeStart={proposeRangeStart}
                exportDays={exportDays}
                onExportDaysChange={setExportDaysWindow}
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
              <div className="rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-3">
                {stepActions}
              </div>
            </div>
          )}

          {planStep === "done" && (
            <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 space-y-4">
              <div>
                <h2 className="text-sm font-semibold text-foreground">
                  {focusShell ? "3 · Ready" : "4 · Apply"}
                </h2>
              </div>
              {focusShell ? (
                <div className="space-y-3">
                  <p className="text-sm text-emerald-200">
                    Routines and goals are Focus-native. Edit blocks on Calendar — SoftLand follows active plan blocks via the enforcer.
                  </p>
                  <button
                    type="button"
                    onClick={() => setTab("calendar")}
                    className="rounded-xl bg-primary px-4 py-2.5 text-xs font-medium text-primary-foreground hover:bg-primary/90"
                  >
                    Open Calendar
                  </button>
                </div>
              ) : finishDone ? (
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
              {stepActions}
            </div>
          )}

          {planStep === "sync" && !focusShell && (
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
              <div className="rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-3">
                {stepActions}
              </div>
            </div>
          )}
              </>
            );
          })()}

          </div>
        </div>
        </ResizablePanel>

        <ResizableHandle
          withHandle
          className="mx-1 bg-border/40 data-[resize-handle-active]:bg-primary/50"
        />

        {/* Right: planning calendar */}
        <ResizablePanel defaultSize={56} minSize={32} className="min-w-0">
        <div className="min-h-0 h-full min-w-0 rounded-2xl border border-white/10 bg-white/[0.03] p-4 pl-3 space-y-3 xl:max-h-[calc(100vh-5.5rem)] xl:overflow-y-auto">
          <div className="flex items-center justify-between gap-2 px-0.5">
            <div>
              <h2 className="text-sm font-semibold text-foreground">Schedule preview</h2>
              <p className="text-[11px] text-muted-foreground mt-0.5">
                {proposed?.length
                  ? "2D day grid · minute-positioned blocks · dashed = draft · Timeline edit for drag/move"
                  : "Today’s blocks live here — generate a schedule, draft auto plan, or click an hour to add."}
              </p>
            </div>
          </div>
          <Suspense fallback={<p className="text-sm text-muted-foreground px-2 py-4">Opening calendar…</p>}>
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
          </Suspense>
        </div>
        </ResizablePanel>
      </ResizablePanelGroup>
      )}

      {tab === "settings" && (
      <ProductivitySettingsTab
        section={settingsSection}
        onSectionChange={setSettingsSection}
        plannerRefresh={plannerRefresh}
        bumpPlanner={bumpPlanner}
        onPolicySaved={() => {
          setPlannerRefresh((n) => n + 1);
          void load();
        }}
        timeline={timeline}
        plannerDayApi={toApiDay(plannerDay)}
        trackerNoData={trackerStatus === "no_data"}
        onLoad={() => void load()}
        onDemoChanged={() => {
          setPlannerRefresh((n) => n + 1);
          if (!focusShell) {
            void fetchDemoClock()
              .then(setDemoClock)
              .catch(() => setDemoClock(null));
          }
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
        exportHint={exportHint}
        exportDays={exportDays}
        exportStartDay={exportStartDay}
        exportEndDay={exportEndDay}
        exporting={exporting}
        applyExportWindow={applyExportWindow}
        setExportDaysWindow={setExportDaysWindow}
        exportWeek={exportWeek}
        toApiDay={toApiDay}
      />
      )}

    </div>
    </div>
    {focusShell ? <MorningBibleOverlay /> : null}
    {focusShell ? <MorningPlanOverlay /> : null}
    {focusShell ? <BedtimeOverlay /> : null}
    </>
  );
}

export default ProductivityPage;
