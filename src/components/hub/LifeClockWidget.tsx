import { useEffect, useId, useMemo, useState, type MouseEvent, type ReactNode } from "react";
import { motion } from "motion/react";
import { ChevronRight, Clock, Loader2, Moon, Zap } from "lucide-react";
import { cn } from "../../app/components/ui/utils";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "../../app/components/ui/tooltip";
import { useTheme } from "../../context/ThemeContext";
import {
  fetchHubDaily,
  fetchLifeDaily,
  formatMinutesAsHours,
  type HubDailyPayload,
  type HubSegment,
  type LifeDailyApi,
} from "../../api/hubClient";
import { LifeClockOmnitrixFace } from "./LifeClockOmnitrixFace";
import { LifeClockRibbonFace } from "./LifeClockRibbonFace";
import { LifeClockSectographFace } from "./LifeClockSectographFace";
import {
  LIFE_CLOCK_SKINS,
  loadLifeClockSkin,
  nextLifeClockSkin,
  saveLifeClockSkin,
  type LifeClockSkinId,
} from "./lifeClockSkins";

interface Activity {
  type: string;
  label: string;
  startHour: number;
  endHour: number;
  color: string;
  isProductive: boolean;
}

const ACTIVITY_META: Record<string, { label: string; color: string; isProductive: boolean }> = {
  sleep: { label: "Sleep", color: "#6366f1", isProductive: false },
  study: { label: "Study", color: "#14b8a6", isProductive: true },
  math: { label: "Math", color: "#10b981", isProductive: true },
  productive: { label: "Productive", color: "#14b8a6", isProductive: true },
  distraction: { label: "Distraction", color: "#f43f5e", isProductive: false },
  comms: { label: "Comms", color: "#f59e0b", isProductive: false },
  break: { label: "Break", color: "#8b5cf6", isProductive: false },
  relaxation: { label: "Break", color: "#8b5cf6", isProductive: false },
  other: { label: "Other", color: "#64748b", isProductive: false },
  idle: { label: "Idle / off", color: "#334155", isProductive: false },
  untracked: { label: "Other", color: "#64748b", isProductive: false },
  elapsed: { label: "Elapsed", color: "#475569", isProductive: false },
  remaining: { label: "Remaining", color: "#1e293b", isProductive: false },
};

/** Stitch themes still use litmus hues for activity types (readable day quality). */
const MIDNIGHT_AMBER_META: Record<string, { label: string; color: string; isProductive: boolean }> = {
  ...ACTIVITY_META,
  sleep: { label: "Sleep", color: "#818cf8", isProductive: false },
};

const OCEANIC_META: Record<string, { label: string; color: string; isProductive: boolean }> = {
  ...ACTIVITY_META,
  sleep: { label: "Sleep", color: "#22d3ee", isProductive: false },
};

const FALLBACK_META = {
  elapsed: { label: "Elapsed (no tracker yet)", color: "#475569", isProductive: false },
  remaining: { label: "Remaining", color: "#1e293b", isProductive: false },
};

type ClockVariant = "default" | "midnight-amber" | "oceanic-aurora";

function clockVariantFromAccent(accent: string, dark: boolean): ClockVariant {
  if (!dark) return "default";
  if (accent === "midnight-amber" || accent === "amber") return "midnight-amber";
  if (accent === "oceanic-aurora") return "oceanic-aurora";
  return "default";
}

const RING_R = 41.5;
/** Quiet trough — activity paints a thinner ribbon inside it */
const RING_STROKE = 6.5;
const RING_STROKE_COMPACT = 5.5;
const ACTIVITY_INSET = 1.15;
/** Seam between painted blocks (hours) */
const SEGMENT_GAP_H = 0.06;

function hourToRad(hour: number): number {
  return (hour / 24) * 2 * Math.PI - Math.PI / 2;
}

function polar(cx: number, cy: number, r: number, hour: number): { x: number; y: number } {
  const a = hourToRad(hour);
  return { x: cx + r * Math.cos(a), y: cy + r * Math.sin(a) };
}

/** Clean radial wedge — no round caps (those read as cluttered pills). */
function ringWedgePath(
  cx: number,
  cy: number,
  rInner: number,
  rOuter: number,
  startHour: number,
  endHour: number,
): string {
  const dur = Math.max(0, endHour - startHour);
  if (dur <= 0.0001 || rOuter <= rInner) return "";
  const o0 = polar(cx, cy, rOuter, startHour);
  const o1 = polar(cx, cy, rOuter, endHour);
  const i1 = polar(cx, cy, rInner, endHour);
  const i0 = polar(cx, cy, rInner, startHour);
  const large = dur / 24 > 0.5 ? 1 : 0;
  return [
    `M ${o0.x} ${o0.y}`,
    `A ${rOuter} ${rOuter} 0 ${large} 1 ${o1.x} ${o1.y}`,
    `L ${i1.x} ${i1.y}`,
    `A ${rInner} ${rInner} 0 ${large} 0 ${i0.x} ${i0.y}`,
    "Z",
  ].join(" ");
}

function formatDurationHours(startHour: number, endHour: number): string {
  const mins = Math.max(1, Math.round((endHour - startHour) * 60));
  if (mins < 60) return `${mins}m`;
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return m ? `${h}h ${m}m` : `${h}h`;
}

const QUADRANT_HOURS = [
  { h: 0, label: "00" },
  { h: 6, label: "06" },
  { h: 12, label: "12" },
  { h: 18, label: "18" },
] as const;

/** Types that deserve ink on the ring — idle/empty stay as quiet trough. */
const RING_SIGNAL_TYPES = new Set([
  "sleep",
  "productive",
  "study",
  "math",
  "distraction",
  "comms",
  "break",
  "relaxation",
  "other",
]);

function aggregateLegend(
  activities: Activity[],
): { type: string; label: string; color: string; minutes: number }[] {
  const map = new Map<string, { type: string; label: string; color: string; minutes: number }>();
  for (const a of activities) {
    if (a.type === "remaining" || a.type === "elapsed") continue;
    const mins = Math.round((a.endHour - a.startHour) * 60);
    if (mins < 1) continue;
    const prev = map.get(a.type);
    if (prev) prev.minutes += mins;
    else map.set(a.type, { type: a.type, label: a.label, color: a.color, minutes: mins });
  }
  return [...map.values()].sort((a, b) => b.minutes - a.minutes);
}


function localDateString(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function formatClockTime(hour: number) {
  const h = Math.floor(hour);
  const m = Math.round((hour - h) * 60);
  return `${h.toString().padStart(2, "0")}:${m.toString().padStart(2, "0")}`;
}

function segmentsToActivities(segments: HubSegment[], variant: ClockVariant): Activity[] {
  const palette =
    variant === "midnight-amber"
      ? MIDNIGHT_AMBER_META
      : variant === "oceanic-aurora"
        ? OCEANIC_META
        : ACTIVITY_META;
  return segments.map((s) => {
    const type = s.type || "untracked";
    const meta = palette[type] || palette.untracked;
    return {
      type,
      label: s.label || meta.label,
      startHour: s.startHour,
      endHour: s.endHour,
      // Litmus colors by activity type (server color as backup)
      color: meta.color || s.color || palette.untracked.color,
      isProductive: meta.isProductive,
    };
  });
}

/** Merge overlaps + flecks; drop idle so the trough stays calm. */
function cleanActivitiesForRing(
  raw: Activity[],
  minMinutes = 12,
  opts?: { quantizeMin?: number },
): Activity[] {
  if (!raw.length) return raw;
  const minH = minMinutes / 60;
  const ordered = [...raw]
    .filter((a) => a.endHour > a.startHour && RING_SIGNAL_TYPES.has(a.type))
    .sort((a, b) => a.startHour - b.startHour || a.endHour - b.endHour);

  const prio: Record<string, number> = {
    sleep: 70,
    productive: 60,
    study: 60,
    math: 60,
    distraction: 50,
    comms: 40,
    break: 30,
    relaxation: 30,
    other: 20,
  };
  const nonOverlap: Activity[] = [];
  for (const seg of ordered) {
    let start = seg.startHour;
    const end = seg.endHour;
    if (nonOverlap.length) {
      const prev = nonOverlap[nonOverlap.length - 1];
      if (start < prev.endHour) {
        const prevP = prio[prev.type] ?? 0;
        const curP = prio[seg.type] ?? 0;
        if (curP > prevP) {
          prev.endHour = start;
          if (prev.endHour <= prev.startHour) nonOverlap.pop();
        } else {
          start = prev.endHour;
        }
      }
    }
    if (end - start < 1 / 60) continue;
    nonOverlap.push({ ...seg, startHour: start, endHour: end });
  }

  const quantizeMin = opts?.quantizeMin;
  if (!quantizeMin || quantizeMin <= 0) {
    const out: Activity[] = [];
    for (const seg of nonOverlap) {
      const dur = seg.endHour - seg.startHour;
      if (out.length && dur < minH) {
        out[out.length - 1].endHour = Math.max(out[out.length - 1].endHour, seg.endHour);
        continue;
      }
      if (
        out.length &&
        out[out.length - 1].type === seg.type &&
        seg.startHour - out[out.length - 1].endHour <= minH
      ) {
        out[out.length - 1].endHour = Math.max(out[out.length - 1].endHour, seg.endHour);
        continue;
      }
      out.push({ ...seg });
    }
    return out.filter((a) => a.endHour - a.startHour >= minH * 0.4);
  }

  const bin = quantizeMin / 60;
  const painted: Activity[] = [];
  for (const seg of nonOverlap) {
    const s0 = Math.floor(seg.startHour / bin) * bin;
    const s1 = Math.ceil(seg.endHour / bin) * bin;
    if (s1 - s0 < minH * 0.75) continue;
    const last = painted[painted.length - 1];
    if (last && last.type === seg.type && s0 <= last.endHour + bin * 0.5) {
      last.endHour = Math.max(last.endHour, s1);
      continue;
    }
    painted.push({ ...seg, startHour: s0, endHour: Math.min(24, s1) });
  }
  return painted.filter((a) => a.endHour - a.startHour >= minH * 0.5);
}

type LifeClockWidgetProps = {
  /** Inside dashboard card — hide outer chrome */
  embedded?: boolean;
  /** Smaller ring for Life Tracker header */
  compact?: boolean;
  showLegend?: boolean;
};

export function LifeClockWidget({
  embedded = false,
  compact = false,
  showLegend = !compact,
}: LifeClockWidgetProps) {
  const { accentColor, isDarkMode } = useTheme();
  const clockVariant = clockVariantFromAccent(accentColor, isDarkMode);
  const stitchRing = clockVariant !== "default";
  const midnightAmber = clockVariant === "midnight-amber";
  const oceanic = clockVariant === "oceanic-aurora";
  const dashboard = embedded && !compact;

  const [now, setNow] = useState(() => new Date());
  const [hub, setHub] = useState<HubDailyPayload | null>(null);
  const [life, setLife] = useState<LifeDailyApi | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [skin, setSkin] = useState<LifeClockSkinId>(() =>
    typeof window !== "undefined" ? loadLifeClockSkin() : "classic",
  );

  const cycleSkin = (e: MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    const next = nextLifeClockSkin(skin);
    setSkin(next);
    saveLifeClockSkin(next);
  };

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(false);
    const load = () => {
      setError(false);
      Promise.all([fetchHubDaily("today"), fetchLifeDaily("today")])
        .then(([payload, lifePayload]) => {
          if (!cancelled) {
            setHub(payload);
            setLife(lifePayload);
            setError(!payload);
          }
        })
        .catch(() => {
          if (!cancelled) setError(true);
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
    };
    load();
    // Refresh often so the litmus ring tracks desktop activity
    const poll = window.setInterval(load, 60_000);
    const onRefresh = () => load();
    window.addEventListener("hub:refresh", onRefresh);
    return () => {
      cancelled = true;
      window.clearInterval(poll);
      window.removeEventListener("hub:refresh", onRefresh);
    };
  }, []);

  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  const localCurrentHour = now.getHours() + now.getMinutes() / 60 + now.getSeconds() / 3600;
  const localTimeLeft = Math.max(0, 24 - localCurrentHour);
  const localPercentElapsed = Math.round((localCurrentHour / 24) * 1000) / 10;
  const hasLifeLog = Boolean(life && !life.empty);

  const activities = useMemo(() => {
    if (hub?.segments?.length) {
      return cleanActivitiesForRing(segmentsToActivities(hub.segments, clockVariant), 12, {
        quantizeMin: 15,
      });
    }
    const elapsed = Math.max(0, Math.min(24, localCurrentHour));
    return [
      {
        type: "elapsed",
        label: FALLBACK_META.elapsed.label,
        startHour: 0,
        endHour: elapsed,
        color: FALLBACK_META.elapsed.color,
        isProductive: false,
      },
      {
        type: "remaining",
        label: FALLBACK_META.remaining.label,
        startHour: elapsed,
        endHour: 24,
        color: FALLBACK_META.remaining.color,
        isProductive: false,
      },
    ].filter((a) => a.endHour > a.startHour);
  }, [hub, clockVariant, localCurrentHour]);

  /** Omnitrix / Sectograph: denser tracker pour (real colors, less quantize). */
  const pourActivities = useMemo(() => {
    if (!hub?.segments?.length) return activities;
    return cleanActivitiesForRing(segmentsToActivities(hub.segments, clockVariant), 3, {
      quantizeMin: 0,
    });
  }, [hub, clockVariant, activities]);

  const currentHour = localCurrentHour;

  const stats = useMemo(() => {
    const studyMinutes = life?.study_minutes ?? 0;
    const exerciseMinutes = life?.exercise_minutes ?? 0;
    const sleepMinutes = Math.round((life?.sleep_hours ?? 0) * 60);
    const trackerProductive =
      hub?.stats?.tracker_productive_minutes ?? hub?.productive_minutes ?? 0;
    const productiveMinutes =
      trackerProductive > 0 ? trackerProductive : studyMinutes + exerciseMinutes;
    if (hub) {
      return {
        productiveMinutes,
        sleepMinutes: sleepMinutes || hub.sleep_minutes || 0,
        timeLeft: localTimeLeft,
        percentElapsed: localPercentElapsed,
        lifeScore: life?.life_score ?? hub.life_score,
        studyMinutes,
        exerciseMinutes,
        moodScore: life?.mood_score ?? 0,
        mathAttempts: hub.math_attempts ?? hub.stats?.math_attempts ?? 0,
        vocabEvents: hub.vocab_events ?? hub.stats?.vocab_events ?? 0,
        litmus: Boolean(
          hub.segments?.some((s) =>
            ["productive", "distraction", "comms", "other", "idle"].includes(s.type || ""),
          ),
        ),
      };
    }
    const passed = activities.filter((a) => a.endHour <= currentHour);
    const productiveHours = passed
      .filter((a) => a.isProductive)
      .reduce((s, a) => s + (a.endHour - a.startHour), 0);
    const sleepHours = passed
      .filter((a) => a.type === "sleep")
      .reduce((s, a) => s + (a.endHour - a.startHour), 0);
    return {
      productiveMinutes: Math.round(productiveHours * 60),
      sleepMinutes: Math.round(sleepHours * 60),
      timeLeft: localTimeLeft,
      percentElapsed: localPercentElapsed,
      lifeScore: 0,
      studyMinutes: 0,
      exerciseMinutes: 0,
      moodScore: 0,
      mathAttempts: 0,
      vocabEvents: 0,
      litmus: false,
    };
  }, [hub, life, activities, currentHour, localTimeLeft, localPercentElapsed]);

  const legendSummary = useMemo(() => aggregateLegend(activities), [activities]);

  const focusShare = useMemo(() => {
    const elapsed = Math.max(0.01, currentHour);
    const focusH = activities
      .filter((a) => a.isProductive && a.endHour > 0)
      .reduce((s, a) => {
        const end = Math.min(a.endHour, currentHour);
        const start = Math.min(a.startHour, currentHour);
        return s + Math.max(0, end - start);
      }, 0);
    return Math.round((focusH / elapsed) * 100);
  }, [activities, currentHour]);

  const strokeW = compact ? RING_STROKE_COMPACT : RING_STROKE;
  const size = compact ? 128 : dashboard ? 220 : 288;
  const hasLoggedSegments = Boolean(hub?.segments?.length);
  const displayDate = localDateString(now);
  const rOuter = RING_R + strokeW / 2;
  const rInner = RING_R - strokeW / 2;
  const nowDot = polar(50, 50, RING_R, currentHour);
  const nowInner = polar(50, 50, rInner - 0.8, currentHour);
  const clockLabel = `${now.getHours().toString().padStart(2, "0")}:${now.getMinutes().toString().padStart(2, "0")}`;
  const skinLabel = LIFE_CLOCK_SKINS.find((s) => s.id === skin)?.label ?? "Classic";
  const svgUid = useId().replace(/:/g, "");
  const dialGrad = `lc-dial-${svgUid}`;
  const glassGrad = `lc-glass-${svgUid}`;
  const trackGrad = `lc-track-${svgUid}`;
  const bezelGrad = `lc-bezel-${svgUid}`;

  const classicRing = (
    <TooltipProvider delayDuration={160}>
      <div
        className={cn(
          "relative shrink-0",
          compact ? "w-32 h-32" : dashboard ? "w-56 h-56" : "w-72 h-72",
        )}
      >
        <svg
          width={size}
          height={size}
          viewBox="0 0 100 100"
          className="w-full h-full drop-shadow-[0_8px_20px_rgba(0,0,0,0.4)]"
          role="img"
          aria-label="24-hour life timeline"
        >
          <defs>
            <radialGradient id={dialGrad} cx="38%" cy="32%" r="72%">
              <stop offset="0%" stopColor="#1e293b" />
              <stop offset="55%" stopColor="#0f172a" />
              <stop offset="100%" stopColor="#020617" />
            </radialGradient>
            <linearGradient id={bezelGrad} x1="20%" y1="0%" x2="80%" y2="100%">
              <stop offset="0%" stopColor="#94a3b8" stopOpacity="0.55" />
              <stop offset="40%" stopColor="#334155" stopOpacity="0.9" />
              <stop offset="100%" stopColor="#64748b" stopOpacity="0.4" />
            </linearGradient>
            <linearGradient id={trackGrad} x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="#0f172a" />
              <stop offset="100%" stopColor="#1e293b" />
            </linearGradient>
            <linearGradient id={glassGrad} x1="50%" y1="0%" x2="50%" y2="55%">
              <stop offset="0%" stopColor="#fff" stopOpacity="0.14" />
              <stop offset="100%" stopColor="#fff" stopOpacity="0" />
            </linearGradient>
          </defs>

          {/* Slim bezel */}
          <circle cx="50" cy="50" r={rOuter + 3.4} fill={`url(#${bezelGrad})`} />
          <circle cx="50" cy="50" r={rOuter + 2.2} fill="#020617" />

          {/* Dial */}
          <circle cx="50" cy="50" r={rInner - 0.6} fill={`url(#${dialGrad})`} />

          {/* Quiet trough — empty reads as calm, not clutter */}
          <circle
            cx="50"
            cy="50"
            r={RING_R}
            fill="none"
            stroke={`url(#${trackGrad})`}
            strokeWidth={strokeW + 1.2}
          />
          <circle
            cx="50"
            cy="50"
            r={RING_R}
            fill="none"
            stroke="rgba(255,255,255,0.035)"
            strokeWidth={strokeW}
          />

          {/* Progress so far — subtle elapsed wash (not another bar layer) */}
          {currentHour > 0.05 && (
            <path
              d={ringWedgePath(50, 50, rInner + 0.2, rOuter - 0.2, 0, Math.min(24, currentHour))}
              fill="rgba(148,163,184,0.07)"
              className="pointer-events-none"
            />
          )}

          {/* 24 hour ticks */}
          {Array.from({ length: 24 }, (_, h) => {
            const isQuad = h % 6 === 0;
            if (isQuad) return null;
            const a = polar(50, 50, rOuter + 0.35, h);
            const b = polar(50, 50, rOuter + 1.45, h);
            return (
              <line
                key={`h-${h}`}
                x1={a.x}
                y1={a.y}
                x2={b.x}
                y2={b.y}
                stroke="rgba(248,250,252,0.2)"
                strokeWidth={0.5}
                strokeLinecap="round"
              />
            );
          })}

          {/* 4 quadrant lines + labels */}
          {QUADRANT_HOURS.map(({ h, label }) => {
            const a = polar(50, 50, rInner + 0.3, h);
            const b = polar(50, 50, rOuter + 2.0, h);
            const lab = polar(50, 50, Math.max(15, rInner - 5.2), h);
            return (
              <g key={`q-${h}`}>
                <line
                  x1={a.x}
                  y1={a.y}
                  x2={b.x}
                  y2={b.y}
                  stroke="rgba(248,250,252,0.42)"
                  strokeWidth={0.95}
                  strokeLinecap="round"
                />
                {!compact && (
                  <text
                    x={lab.x}
                    y={lab.y}
                    textAnchor="middle"
                    dominantBaseline="central"
                    fill="rgba(148,163,184,0.7)"
                    fontSize="3.3"
                    fontFamily="ui-monospace, SFMono-Regular, Menlo, monospace"
                    fontWeight={600}
                    letterSpacing="0.05em"
                  >
                    {label}
                  </text>
                )}
              </g>
            );
          })}

          {/* Signal-only wedges — thin ribbon inside trough */}
          {activities.map((a, idx) => {
            const rawDur = Math.max(0, a.endHour - a.startHour);
            if (rawDur <= 0) return null;
            const pad = rawDur > SEGMENT_GAP_H * 2 ? SEGMENT_GAP_H / 2 : SEGMENT_GAP_H * 0.25;
            const h0 = a.startHour + pad;
            const h1 = a.endHour - pad;
            if (h1 - h0 < 2 / 60) return null;
            const d = ringWedgePath(
              50,
              50,
              rInner + ACTIVITY_INSET,
              rOuter - ACTIVITY_INSET,
              h0,
              h1,
            );
            if (!d) return null;
            const isFuture = a.startHour >= currentHour;
            const tip = `${a.label} · ${formatClockTime(a.startHour)}–${formatClockTime(a.endHour)} · ${formatDurationHours(a.startHour, a.endHour)}`;
            return (
              <Tooltip key={`${a.type}-${idx}-${a.startHour.toFixed(3)}`}>
                <TooltipTrigger asChild>
                  <motion.path
                    d={d}
                    fill={a.color}
                    fillOpacity={isFuture ? 0.28 : 0.88}
                    className="cursor-pointer outline-none"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    whileHover={{ fillOpacity: 1 }}
                    transition={{ duration: 0.25 }}
                    aria-label={tip}
                    tabIndex={0}
                  />
                </TooltipTrigger>
                <TooltipContent
                  side="top"
                  sideOffset={10}
                  className="border border-white/10 bg-zinc-950/95 text-zinc-50 shadow-xl backdrop-blur-md"
                >
                  <div className="flex items-center gap-2">
                    <span
                      className="h-2 w-2 shrink-0 rounded-full ring-1 ring-white/20"
                      style={{ backgroundColor: a.color }}
                    />
                    <span className="font-medium tracking-tight">{a.label}</span>
                  </div>
                  <p className="mt-0.5 font-mono text-[10px] tabular-nums text-zinc-400">
                    {formatClockTime(a.startHour)} – {formatClockTime(a.endHour)}
                    <span className="mx-1.5 text-zinc-600">·</span>
                    {formatDurationHours(a.startHour, a.endHour)}
                  </p>
                </TooltipContent>
              </Tooltip>
            );
          })}

          {/* Glass sheen on dial only */}
          <circle
            cx="50"
            cy="50"
            r={rInner - 1.2}
            fill={`url(#${glassGrad})`}
            className="pointer-events-none"
          />

          {/* Now — fine hand + pip */}
          <line
            x1={nowInner.x}
            y1={nowInner.y}
            x2={nowDot.x}
            y2={nowDot.y}
            stroke="rgba(248,250,252,0.85)"
            strokeWidth={1.15}
            strokeLinecap="round"
            className="pointer-events-none"
          />
          <circle cx={nowDot.x} cy={nowDot.y} r={compact ? 1.8 : 2.35} fill="#f8fafc" />
          <circle cx={nowDot.x} cy={nowDot.y} r={compact ? 0.85 : 1.1} fill="#2dd4bf" />
        </svg>

        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none text-center px-5">
          <span
            className={cn(
              "font-mono font-semibold tabular-nums leading-none tracking-tight text-slate-50",
              compact ? "text-base" : dashboard ? "text-[1.85rem]" : "text-[2rem]",
            )}
          >
            {clockLabel}
          </span>
          {(dashboard || (!compact && !dashboard)) && (
            <span className="mt-1.5 text-[10px] font-medium tracking-wide text-slate-400">
              {stats.timeLeft.toFixed(1)}h left
            </span>
          )}
          {stats.litmus && (dashboard || !compact) && (
            <span className="mt-0.5 text-[10px] font-semibold tabular-nums text-teal-400/95">
              {focusShare}% focus
            </span>
          )}
          {!compact && !dashboard && (
            <span className="mt-1 text-[9px] font-mono text-slate-500">{displayDate}</span>
          )}
        </div>
      </div>
    </TooltipProvider>
  );

  const dayLabel = now
    .toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" })
    .toUpperCase();

  const sectographFace = (
    <LifeClockSectographFace
      size={size}
      compact={compact}
      activities={pourActivities}
      currentHour={currentHour}
      timeLeftHours={stats.timeLeft}
      focusShare={focusShare}
      clockLabel={clockLabel}
      showFocus={dashboard || !compact || stats.litmus}
    />
  );

  const omnitrixFace = (
    <LifeClockOmnitrixFace
      size={size}
      compact={compact}
      activities={pourActivities}
      currentHour={currentHour}
      timeLeftHours={stats.timeLeft}
      focusShare={focusShare}
      clockLabel={clockLabel}
      showFocus={dashboard || !compact || stats.litmus}
    />
  );

  const ribbonFace = (
    <LifeClockRibbonFace
      size={size}
      compact={compact}
      activities={activities}
      currentHour={currentHour}
      timeLeftHours={stats.timeLeft}
      focusShare={focusShare}
      clockLabel={clockLabel}
      showFocus={dashboard || !compact || stats.litmus}
      productiveMinutes={stats.productiveMinutes}
      dayLabel={dayLabel}
    />
  );

  const ring =
    skin === "sectograph"
      ? sectographFace
      : skin === "omnitrix"
        ? omnitrixFace
        : skin === "ribbon"
          ? ribbonFace
          : classicRing;

  const skinPicker = (
    <button
      type="button"
      onClick={cycleSkin}
      onMouseDown={(e) => e.stopPropagation()}
      className={cn(
        "inline-flex items-center gap-1 rounded-full border border-white/10 bg-black/30 px-2 py-0.5",
        "text-[10px] font-medium text-muted-foreground hover:text-foreground hover:border-emerald-500/40",
        "transition-colors",
      )}
      title="Cycle life clock design"
      aria-label={`Life clock skin: ${skinLabel}. Click to change.`}
    >
      {skinLabel}
      <ChevronRight className="h-3 w-3 opacity-70" />
    </button>
  );

  const metricCard = (label: string, value: string, icon: ReactNode) => (
    <div
      className={cn(
        "flex items-center justify-between rounded-2xl",
        dashboard ? "p-3" : "p-4",
        stitchRing ? "life-clock-metric" : "rounded-lg border border-border/50 bg-background/40"
      )}
    >
      <div className="flex items-center gap-2">
        {icon}
        <span className="text-sm text-foreground">{label}</span>
      </div>
      <span className="font-mono font-semibold tabular-nums text-sm">{value}</span>
    </div>
  );

  const metrics = (
    <div
      className={cn(
        "flex-1 flex flex-col gap-3 w-full min-w-0",
        dashboard && "gap-2",
        compact && "hidden lg:flex"
      )}
    >
      {metricCard(
        "Productive",
        formatMinutesAsHours(stats.productiveMinutes),
        <Zap className={cn("w-4 h-4", midnightAmber ? "text-secondary" : "text-muted-foreground")} />
      )}
      {metricCard(
        "Sleep",
        formatMinutesAsHours(stats.sleepMinutes),
        <Moon className={cn("w-4 h-4", midnightAmber ? "text-primary" : "text-muted-foreground")} />
      )}
      <div
        className={cn(
          "rounded-2xl space-y-2",
          dashboard ? "p-3" : "p-4",
          midnightAmber ? "life-clock-metric" : "rounded-lg border border-border/50 bg-background/40 col-span-2"
        )}
      >
        <div className="flex justify-between text-sm">
          <span>Day progress</span>
          <span className={cn("font-mono tabular-nums", midnightAmber && "text-secondary")}>
            {stats.percentElapsed}%
          </span>
        </div>
        <div
          className={cn(
            "relative h-2 w-full rounded-full overflow-hidden",
            midnightAmber ? "life-clock-progress-track" : "bg-muted"
          )}
          role="progressbar"
          aria-valuenow={stats.percentElapsed}
          aria-valuemin={0}
          aria-valuemax={100}
        >
          <div
            className={cn(
              "absolute inset-y-0 left-0 rounded-full transition-all duration-500",
              midnightAmber ? "life-clock-progress-fill" : "bg-primary/80"
            )}
            style={{ width: `${Math.min(100, stats.percentElapsed)}%` }}
          />
        </div>
        <p className="text-xs text-muted-foreground">{stats.timeLeft.toFixed(1)}h until the day ends</p>
      </div>
      {stats.lifeScore > 0 && (
        <p className="text-center text-sm text-muted-foreground">
          Life score <span className="font-semibold text-foreground">{stats.lifeScore}</span>/100
        </p>
      )}
      <div className={cn("grid gap-2 text-xs", dashboard ? "grid-cols-4" : "grid-cols-2")}>
        <div className="rounded-xl border border-white/10 bg-black/20 p-2">
          <p className="text-muted-foreground">Study</p>
          <p className="font-mono font-semibold">{formatMinutesAsHours(stats.studyMinutes)}</p>
        </div>
        <div className="rounded-xl border border-white/10 bg-black/20 p-2">
          <p className="text-muted-foreground">Exercise</p>
          <p className="font-mono font-semibold">{stats.exerciseMinutes}m</p>
        </div>
        <div className="rounded-xl border border-white/10 bg-black/20 p-2">
          <p className="text-muted-foreground">Math</p>
          <p className="font-mono font-semibold">{stats.mathAttempts}</p>
        </div>
        <div className="rounded-xl border border-white/10 bg-black/20 p-2">
          <p className="text-muted-foreground">Vocab</p>
          <p className="font-mono font-semibold">{stats.vocabEvents}</p>
        </div>
      </div>
    </div>
  );

  const legend = showLegend && hasLoggedSegments && legendSummary.length > 0 && (
    <div className="mt-5 flex flex-wrap gap-2">
      {legendSummary.map((row) => (
        <div
          key={row.type}
          className="inline-flex items-center gap-2 rounded-full border border-border/40 bg-background/30 px-3 py-1.5 text-xs"
        >
          <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: row.color }} />
          <span className="text-foreground/90">{row.label}</span>
          <span className="font-mono tabular-nums text-muted-foreground">
            {formatMinutesAsHours(row.minutes)}
          </span>
        </div>
      ))}
    </div>
  );

  if (loading) {
    return (
      <div className={cn(!embedded && "gloss-panel rounded-2xl p-5", "flex items-center justify-center gap-2 py-12")}>
        <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
        <span className="text-sm text-muted-foreground">Loading today&apos;s timeline…</span>
      </div>
    );
  }

  if (error && !hub) {
    return (
      <div className={cn(!embedded && "gloss-panel rounded-2xl p-5", "text-center py-8 space-y-2")}>
        <p className="text-sm text-muted-foreground">Could not load today&apos;s timeline.</p>
        <button
          type="button"
          className="text-sm text-primary hover:underline"
          onClick={() => window.location.reload()}
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div
      className={cn(
        !embedded && "gloss-panel rounded-2xl p-5 md:p-8",
        midnightAmber && !embedded && "life-clock-panel--amber"
      )}
    >
      {!embedded && !compact && (
        <div className="text-center mb-4 relative">
          <h3 className="text-lg font-semibold">24-hour life clock</h3>
          <p className="text-sm text-muted-foreground">Track how your day is unfolding</p>
          <div className="mt-2 flex justify-center">{skinPicker}</div>
        </div>
      )}
      {(embedded || compact) && (
        <div className="mb-2 flex justify-end" onClick={(e) => e.stopPropagation()}>
          {skinPicker}
        </div>
      )}
      <div
        className={cn(
          "flex gap-4 items-start",
          compact ? "flex-row" : "flex-col lg:flex-row gap-6"
        )}
      >
        {ring}
        {skin === "classic" ? metrics : !compact && metrics}
      </div>
      {!hasLifeLog && !hasLoggedSegments && (
        <div className="mt-4 rounded-xl border border-amber-500/20 bg-amber-500/10 px-3 py-2 text-sm text-muted-foreground">
          <Clock className="w-4 h-4 inline mr-1.5 text-amber-300" />
          Start the desktop tracker — the ring becomes a litmus of your day (teal = focus, rose =
          distraction).
        </div>
      )}
      {hasLoggedSegments && !showLegend && skin === "classic" && (
        <p className="mt-3 text-[11px] text-muted-foreground flex flex-wrap gap-x-3 gap-y-1">
          <span className="inline-flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-teal-400" /> Focus
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-rose-400" /> Distraction
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-amber-400" /> Comms
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-indigo-400" /> Sleep
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-slate-500" /> Idle
          </span>
        </p>
      )}
      {hasLoggedSegments && skin === "sectograph" && !showLegend && (
        <p className="mt-2 text-[10px] text-slate-400/90 font-mono text-center">
          Sectograph — day as clock sectors · hover a slice
        </p>
      )}
      {hasLoggedSegments && skin === "ribbon" && !showLegend && (
        <p className="mt-2 text-[10px] text-cyan-300/80 font-mono text-center italic">
          what you do is what you become
        </p>
      )}
      {hasLoggedSegments && skin === "omnitrix" && !showLegend && (
        <p className="mt-2 text-[10px] text-emerald-400/80 font-mono text-center">
          Omnitrix — green hourglass = day pour · black wings = readout
        </p>
      )}
      {legend}
    </div>
  );
}
