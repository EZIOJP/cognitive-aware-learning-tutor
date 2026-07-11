import { useState, useEffect, useCallback } from "react";
import {
  Monitor, Globe, RefreshCw, AlertCircle, CheckCircle2,
  Clock, Zap, BarChart2, Terminal, Code2, BookOpen, PenLine,
  Gamepad2, Music, MessageSquare, FileText, Folder, Cpu, CalendarDays,
  ChevronDown, ChevronRight, Download, Loader2,
} from "lucide-react";
import { fetchDesktopStats, fetchBrowserStats, fetchTrackerHealth, fetchDesktopTimeline, forceTrackerSync } from "../api/behaviorClient";
import type { DesktopStats, BrowserStats, AppSession, BrowserSite, TrackerHealth, DesktopTimeline } from "../api/behaviorClient";
import { PlannerCalendar } from "../components/productivity/PlannerCalendar";
import { CalendarInfographics } from "../components/productivity/CalendarInfographics";
import { PlanVsActualDashboard } from "../components/productivity/PlanVsActualDashboard";
import { TimetablePanel } from "../components/productivity/TimetablePanel";
import { TodayPanel } from "../components/productivity/TodayPanel";
import { RoutinesPanel } from "../components/productivity/RoutinesPanel";
import { Link } from "react-router";
import {
  fetchAdherence,
  createPlannerBlock,
  downloadProductivityWeekExport,
  type AdherenceSummary,
} from "../api/plannerClient";
import { fetchDueReview } from "../api/globalQuizClient";
import ClassificationReview from "../components/productivity/ClassificationReview";

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

function AppRow({ session, maxSeconds }: { session: AppSession; maxSeconds: number }) {
  const pct = maxSeconds > 0 ? (session.seconds / maxSeconds) * 100 : 0;
  return (
    <div className="flex items-center gap-3 py-2">
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
    <div className="flex items-center gap-3 py-1.5 pl-6">
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
        <div className="flex items-center gap-2">
          {open ? <ChevronDown size={14} className="text-muted-foreground" /> : <ChevronRight size={14} className="text-muted-foreground" />}
          <div className="flex-1">
            <AppRow session={session} maxSeconds={maxSeconds} />
          </div>
        </div>
      </button>
      {open && sites.length > 0 && (
        <div className="border-l border-white/10 ml-2 mb-1">
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
  const [tab, setTab] = useState<"calendar" | "schedule" | "overview">("calendar");
  const [plannerRefresh, setPlannerRefresh] = useState(0);
  const [syncing, setSyncing] = useState(false);
  const [syncHint, setSyncHint] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [exportHint, setExportHint] = useState<string | null>(null);

  const loadAdherence = useCallback(async (day: Date) => {
    try {
      const a = await fetchAdherence(day);
      setAdherence(a);
    } catch {
      setAdherence(null);
    }
  }, []);

  const bumpPlanner = useCallback(() => {
    setPlannerRefresh((k) => k + 1);
    void loadAdherence(plannerDay);
  }, [plannerDay, loadAdherence]);

  const loadDue = useCallback(async () => {
    try {
      const d = await fetchDueReview(5);
      setDueReviews(d.count ?? d.items?.length ?? 0);
    } catch {
      setDueReviews(0);
    }
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    setLoadErrors([]);
    const results = await Promise.allSettled([
      fetchDesktopStats(),
      fetchBrowserStats(),
      fetchTrackerHealth(),
      fetchDesktopTimeline(),
    ]);
    const labels = ["desktop-stats", "browser stats", "tracker-health", "desktop-timeline"];
    const failures: string[] = [];

    if (results[0].status === "fulfilled") setDesktop(results[0].value);
    else failures.push(`${labels[0]}: ${results[0].reason instanceof Error ? results[0].reason.message : "failed"}`);

    if (results[1].status === "fulfilled") setBrowser(results[1].value);
    else failures.push(`${labels[1]}: ${results[1].reason instanceof Error ? results[1].reason.message : "failed"}`);

    if (results[2].status === "fulfilled") setTrackerHealth(results[2].value);
    else failures.push(`${labels[2]}: ${results[2].reason instanceof Error ? results[2].reason.message : "failed"}`);

    if (results[3].status === "fulfilled") setTimeline(results[3].value);
    else failures.push(`${labels[3]}: ${results[3].reason instanceof Error ? results[3].reason.message : "failed"}`);

    if (failures.length === 4) {
      setError(failures[0] ?? "Failed to load stats");
    } else if (failures.length > 0) {
      setLoadErrors(failures);
    }
    setLastRefresh(new Date());
    setLoading(false);
  }, []);

  const syncTracker = useCallback(async () => {
    setSyncing(true);
    setSyncHint(null);
    try {
      const result = await forceTrackerSync();
      await load();
      void loadAdherence(plannerDay);
      setPlannerRefresh((k) => k + 1);
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
  }, [load, loadAdherence, plannerDay]);

  const exportWeek = useCallback(async (format: "json" | "csv") => {
    setExporting(true);
    setExportHint(null);
    try {
      await downloadProductivityWeekExport(7, format);
      setExportHint(format === "csv" ? "CSV downloaded" : "JSON downloaded");
      setTimeout(() => setExportHint(null), 3000);
    } catch (e: unknown) {
      setExportHint(e instanceof Error ? e.message : "Export failed");
      setTimeout(() => setExportHint(null), 4000);
    } finally {
      setExporting(false);
    }
  }, []);

  useEffect(() => {
    load();
    void loadDue();
    const id = setInterval(load, 30_000); // auto-refresh every 30s
    return () => clearInterval(id);
  }, [load, loadDue]);

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
      <div className={`mx-auto space-y-6 pb-20 ${tab === "calendar" ? "max-w-7xl" : "max-w-6xl"}`}>

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Monitor size={22} className="text-primary" />
            Productivity Tracker
          </h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Calendar · import schedules · screen-time
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex rounded-lg border border-white/10 overflow-hidden text-xs">
            {([
              { id: "calendar" as const, label: "Calendar" },
              { id: "schedule" as const, label: "Import & routines" },
              { id: "overview" as const, label: "Screen time" },
            ]).map(({ id, label }) => (
              <button
                key={id}
                type="button"
                onClick={() => setTab(id)}
                className={`px-3 py-1.5 ${tab === id ? "bg-white/10 text-foreground" : "text-muted-foreground hover:bg-white/5"}`}
              >
                {label}
              </button>
            ))}
          </div>
          <span className="text-xs text-muted-foreground">
            Refreshed {lastRefresh.toLocaleTimeString()}
          </span>
          {trackerHealth?.last_event_at && (
            <span className="text-[11px] text-muted-foreground hidden sm:inline">
              Last tracked {new Date(trackerHealth.last_event_at).toLocaleTimeString()}
            </span>
          )}
          {syncHint && (
            <span className="text-xs text-emerald-400 max-w-[200px] truncate" title={syncHint}>
              {syncHint}
            </span>
          )}
          {exportHint && (
            <span className="text-xs text-sky-400 max-w-[200px] truncate" title={exportHint}>
              {exportHint}
            </span>
          )}
          <div className="flex rounded-lg border border-white/10 overflow-hidden text-xs">
            <button
              type="button"
              disabled={exporting}
              onClick={() => void exportWeek("json")}
              className="flex items-center gap-1 px-2.5 py-1.5 hover:bg-white/10 disabled:opacity-50"
              title="Export last 7 days (JSON) — patterns for building a timetable"
            >
              {exporting ? <Loader2 size={12} className="animate-spin" /> : <Download size={12} />}
              7d JSON
            </button>
            <button
              type="button"
              disabled={exporting}
              onClick={() => void exportWeek("csv")}
              className="flex items-center gap-1 px-2.5 py-1.5 border-l border-white/10 hover:bg-white/10 disabled:opacity-50"
              title="Export last 7 days (CSV) for spreadsheet timetable drafting"
            >
              7d CSV
            </button>
          </div>
          <button
            type="button"
            onClick={() => void syncTracker()}
            disabled={syncing || loading}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-violet-600/80 hover:bg-violet-600 text-sm transition-colors disabled:opacity-50"
            title="Flush current tracker session and reload stats"
          >
            <Zap size={13} className={syncing ? "animate-pulse" : ""} />
            Sync tracker
          </button>
          <button
            onClick={load}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-sm border border-white/10 transition-colors disabled:opacity-50"
          >
            <RefreshCw size={13} className={loading ? "animate-spin" : ""} />
            Refresh
          </button>
        </div>
      </div>

      {/* Tracker status banner */}
      <div className={`flex items-center gap-3 p-3 rounded-xl border ${
        trackerRunning
          ? "border-emerald-500/30 bg-emerald-500/5"
          : trackerStale
            ? "border-yellow-500/30 bg-yellow-500/5"
            : "border-orange-500/30 bg-orange-500/5"
      }`}>
        {trackerRunning
          ? <CheckCircle2 size={16} className="text-emerald-400 shrink-0" />
          : trackerStale
            ? <Clock size={16} className="text-yellow-400 shrink-0" />
            : <AlertCircle size={16} className="text-orange-400 shrink-0" />
        }
        <div className="flex-1 min-w-0">
          {trackerRunning ? (
            <span className="text-sm text-emerald-300">
              Standalone tracker is <strong>running</strong>
              {trackerHealth?.last_event_at && (
                <> · last activity {new Date(trackerHealth.last_event_at).toLocaleTimeString()}</>
              )}
            </span>
          ) : trackerStale ? (
            <span className="text-sm text-yellow-300">
              Tracker data is <strong>stale</strong> — last activity{" "}
              {trackerHealth?.last_event_at
                ? new Date(trackerHealth.last_event_at).toLocaleString()
                : "unknown"}
              . Try <strong>Sync tracker</strong> or run{" "}
              <code className="bg-black/40 px-1 rounded text-xs font-mono">scripts\desktop_tracker\run_desktop_tracker_headless.bat</code>
              {trackerHealth?.hint && (
                <span className="block mt-1 text-xs text-yellow-200/90">{trackerHealth.hint}</span>
              )}
            </span>
          ) : (
            <span className="text-sm text-orange-300">
              Tracker not installed or no data yet. Run once:{" "}
              <code className="bg-black/40 px-1.5 py-0.5 rounded text-xs font-mono">
                scripts\install_tracker_startup.bat
              </code>
              {" "}or headless{" "}
              <code className="bg-black/40 px-1.5 py-0.5 rounded text-xs font-mono">
                scripts\desktop_tracker\run_desktop_tracker_headless.bat
              </code>
            </span>
          )}
        </div>
      </div>

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

      {/* KPI row — screen time overview only */}
      {tab === "overview" && (
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">

        {/* Productivity score ring */}
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
            <div className="text-xs text-muted-foreground mt-0.5">weighted by time</div>
          </div>
        </div>

        <div className="bg-white/[0.03] border border-white/10 rounded-2xl p-5 flex flex-col gap-1 justify-center">
          <Clock size={18} className="text-blue-400 mb-1" />
          <div className="text-2xl font-bold">{totalHours}h</div>
          <div className="text-xs text-muted-foreground">Tracked today</div>
        </div>

        <div className="bg-white/[0.03] border border-white/10 rounded-2xl p-5 flex flex-col gap-1 justify-center">
          <BarChart2 size={18} className="text-purple-400 mb-1" />
          <div className="text-2xl font-bold">{desktop?.sessions.length ?? 0}</div>
          <div className="text-xs text-muted-foreground">Apps used</div>
        </div>

        <div className="bg-white/[0.03] border border-white/10 rounded-2xl p-5 flex flex-col gap-1 justify-center">
          <Zap size={18} className="text-yellow-400 mb-1" />
          <div className="text-2xl font-bold">{browser?.events_today ?? 0}</div>
          <div className="text-xs text-muted-foreground">Browser events</div>
        </div>
      </div>
      )}

      {tab === "calendar" && (
      <div className="space-y-6">
        {!trackerRunning && trackerStatus === "no_data" && (
          <div className="rounded-xl border border-orange-500/30 bg-orange-500/5 p-4 space-y-2">
            <p className="text-sm text-orange-200 font-medium">Desktop tracker is not running</p>
            <p className="text-xs text-orange-200/80">
              Plan vs actual needs tracked sessions. Start the tracker now, then switch apps for ~30s and click{" "}
              <strong>Sync tracker</strong>.
            </p>
            <div className="flex flex-wrap items-center gap-3 text-xs">
              <code className="bg-black/40 px-2 py-1 rounded font-mono">
                scripts\desktop_tracker\run_desktop_tracker_headless.bat
              </code>
              <button
                type="button"
                onClick={() => setTab("overview")}
                className="text-orange-300 hover:underline"
              >
                Full setup on Screen time tab →
              </button>
            </div>
          </div>
        )}

        <div className="w-full mb-4 bg-white/[0.03] border border-white/10 rounded-2xl p-6 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="font-semibold flex items-center gap-2">
              <CalendarDays size={16} className="text-violet-400" />
              Planner calendar
            </h2>
            {adherence && (
              <div className="text-xs text-muted-foreground flex flex-wrap gap-3">
                <span>Planned <strong className="text-foreground">{adherence.planned_minutes}m</strong></span>
                <span>Actual <strong className="text-foreground">{adherence.actual_minutes}m</strong></span>
                <span>Effective focus <strong className="text-foreground">{adherence.effective_focus_minutes ?? 0}m</strong></span>
                <span>Adherence <strong className="text-foreground">{adherence.adherence_pct != null ? `${adherence.adherence_pct}%` : "—"}</strong></span>
              </div>
            )}
          </div>

          <PlannerCalendar
            expanded
            refreshKey={plannerRefresh}
            selectedDay={plannerDay}
            onSelectedDayChange={setPlannerDay}
          />
        </div>

        <TodayPanel
          compact
          refreshKey={plannerRefresh}
          dueReviews={dueReviews}
          onPlannerChange={bumpPlanner}
        />

        <PlanVsActualDashboard
          selectedDay={plannerDay}
          onSelectedDayChange={setPlannerDay}
          refreshKey={plannerRefresh}
          trackerHealth={trackerHealth}
        />

        <CalendarInfographics
          desktop={desktop}
          dueReviews={dueReviews}
          onScheduleReview={() => {
            const start = new Date();
            start.setMinutes(start.getMinutes() + 15 - (start.getMinutes() % 15));
            void createPlannerBlock({
              title: "SRS review",
              category: "review",
              start_at: start.toISOString(),
              duration_minutes: Math.min(30, 15 + dueReviews * 2),
            }).then(() => bumpPlanner());
          }}
        />
      </div>
      )}

      {tab === "schedule" && (
      <div className="space-y-4">
        <div className="flex flex-wrap gap-3 p-3 rounded-xl border border-violet-500/25 bg-violet-500/5 text-sm">
          <span className="text-muted-foreground">Daily rhythm:</span>
          <Link to="/journal" className="text-amber-300 hover:underline flex items-center gap-1">
            <PenLine size={14} /> Journal
          </Link>
        </div>
        <div className="grid gap-6 lg:grid-cols-2">
        <div className="bg-white/[0.03] border border-white/10 rounded-2xl p-6">
          <RoutinesPanel onApplied={bumpPlanner} />
        </div>
        <div className="bg-white/[0.03] border border-white/10 rounded-2xl p-6">
          <TimetablePanel onPlannerUpdated={bumpPlanner} />
        </div>
        </div>
        <div className="bg-white/[0.03] border border-white/10 rounded-2xl p-6">
          <ClassificationReview trackerNoData={trackerStatus === "no_data"} />
        </div>
      </div>
      )}

      {tab === "overview" && (
      <>
      {/* App time breakdown */}
      <div className="bg-white/[0.03] border border-white/10 rounded-2xl p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold flex items-center gap-2">
            <Monitor size={16} className="text-primary" />
            Desktop App Usage
          </h2>
          <div className="flex items-center gap-4 text-xs text-muted-foreground">
            {desktop && (
              <span className="tabular-nums font-medium text-foreground">{fmtSeconds(desktop.total_seconds)} today</span>
            )}
            <span>App / site</span>
            <span className="w-24 text-center">Time</span>
            <span className="text-right">Score</span>
          </div>
        </div>

        {loading && !desktop && (
          <div className="space-y-3">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="h-9 rounded-lg bg-white/5 animate-pulse" />
            ))}
          </div>
        )}

        {!loading && (!desktop?.sessions || desktop.sessions.length === 0) && (
          <div className="text-center py-10 text-muted-foreground text-sm space-y-3">
            <Monitor size={32} className="mx-auto opacity-30" />
            <p>No desktop data yet.</p>
            <p className="text-xs">Install the standalone tracker (runs in system tray):</p>
            <code className="block bg-black/40 px-4 py-2 rounded-lg text-xs font-mono mx-auto w-fit">
              scripts\install_tracker_startup.bat
            </code>
          </div>
        )}

        {timeline && timeline.intervals.length > 0 && (
          <div className="mb-6 pb-6 border-b border-white/5">
            <div className="text-xs text-muted-foreground mb-3 uppercase tracking-wider">Today timeline</div>
            <DayTimeline timeline={timeline} listTotalSeconds={desktop?.total_seconds} />
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

      {/* Browser activity — classified */}
      <div className="bg-white/[0.03] border border-white/10 rounded-2xl p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold flex items-center gap-2">
            <Globe size={16} className="text-sky-400" />
            Browser Activity
          </h2>
          <div className="flex items-center gap-3 text-xs text-muted-foreground">
            {browser?.avg_productivity_score != null && browser.avg_productivity_score > 0 && (
              <span className={`font-bold text-sm ${scoreColor(browser.avg_productivity_score)}`}>
                {browser.avg_productivity_score}
                <span className="font-normal text-[10px] text-muted-foreground ml-0.5">/ 100</span>
              </span>
            )}
            {browser?.source && (
              <span>
                source: {browser.source === "desktop_tracker" || browser.source === "desktop_tracker_csv"
                  ? "desktop tracker (tab titles)"
                  : browser.source}
              </span>
            )}
          </div>
        </div>

        {browser && browser.events_today > 0 ? (
          <>
            {/* Category breakdown */}
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
                    ))
                  }
                </div>
              </div>
            )}

            {/* Top sites with classification */}
            {browser.top_domains.length > 0 && (
              <div>
                <div className="text-xs text-muted-foreground mb-2 uppercase tracking-wider">Top Sites</div>
                <div className="flex items-center gap-4 text-[10px] text-muted-foreground mb-1 px-1">
                  <span className="w-44">Site</span>
                  <span className="flex-1 text-center">Time</span>
                  <span className="w-28 text-right">Category</span>
                  <span className="w-8 text-right">Score</span>
                </div>
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
                            width: `${Math.min(100, (d.seconds / (browser.top_domains[0]?.seconds || 1)) * 100)}%`
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
          <div className="text-center py-8 text-muted-foreground text-sm space-y-2">
            <Globe size={28} className="mx-auto opacity-30" />
            <p>No browser data yet.</p>
            <p className="text-xs">Install the SelfTracker Chrome extension from <code className="font-mono">selftracker-extension/</code></p>
          </div>
        )}
      </div>

      <div className="bg-white/[0.03] border border-white/10 rounded-2xl p-6 space-y-3">
        <h2 className="font-semibold flex items-center gap-2">
          <Terminal size={16} className="text-green-400" />
          Tracker setup
        </h2>
        <ol className="space-y-2 text-sm text-muted-foreground list-decimal list-inside">
          <li>Install at logon: <code className="bg-black/40 px-1.5 py-0.5 rounded text-xs font-mono">scripts\install_tracker_startup.bat</code></li>
          <li>Headless now: <code className="bg-black/40 px-1.5 py-0.5 rounded text-xs font-mono">scripts\desktop_tracker\run_desktop_tracker_headless.bat</code></li>
        </ol>
      </div>
      </>
      )}

    </div>
    </div>
  );
}

export default ProductivityPage;
