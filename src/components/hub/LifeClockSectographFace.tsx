import { useId } from "react";
import { motion } from "motion/react";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "../../app/components/ui/tooltip";
import { cn } from "../../app/components/ui/utils";

export type SectographActivity = {
  type: string;
  label: string;
  startHour: number;
  endHour: number;
  color: string;
  isProductive: boolean;
};

type LifeClockSectographFaceProps = {
  size: number;
  compact?: boolean;
  activities: SectographActivity[];
  currentHour: number;
  timeLeftHours: number;
  focusShare: number;
  clockLabel: string;
  showFocus?: boolean;
};

const CX = 50;
const CY = 50;
/** Inner hole — leaves room for time readout */
const R_INNER = 18;
const R_OUTER = 44;

function hourToRad(hour: number): number {
  return (hour / 24) * 2 * Math.PI - Math.PI / 2;
}

function polar(r: number, hour: number): { x: number; y: number } {
  const a = hourToRad(hour);
  return { x: CX + r * Math.cos(a), y: CY + r * Math.sin(a) };
}

/** Classic Sectograph sector — pie slice of the day. */
function sectorPath(rInner: number, rOuter: number, startH: number, endH: number): string {
  const dur = Math.max(0, endH - startH);
  if (dur <= 0.0001) return "";
  const o0 = polar(rOuter, startH);
  const o1 = polar(rOuter, endH);
  const i1 = polar(rInner, endH);
  const i0 = polar(rInner, startH);
  const large = dur / 24 > 0.5 ? 1 : 0;
  return [
    `M ${o0.x} ${o0.y}`,
    `A ${rOuter} ${rOuter} 0 ${large} 1 ${o1.x} ${o1.y}`,
    `L ${i1.x} ${i1.y}`,
    `A ${rInner} ${rInner} 0 ${large} 0 ${i0.x} ${i0.y}`,
    "Z",
  ].join(" ");
}

function formatClockTime(hour: number) {
  const h = Math.floor(hour);
  const m = Math.round((hour - h) * 60);
  return `${h.toString().padStart(2, "0")}:${m.toString().padStart(2, "0")}`;
}

function formatDuration(startHour: number, endHour: number): string {
  const mins = Math.max(1, Math.round((endHour - startHour) * 60));
  if (mins < 60) return `${mins}m`;
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return m ? `${h}h ${m}m` : `${h}h`;
}

const QUADS = [
  { h: 0, label: "00" },
  { h: 6, label: "06" },
  { h: 12, label: "12" },
  { h: 18, label: "18" },
] as const;

export function LifeClockSectographFace({
  size,
  compact = false,
  activities,
  currentHour,
  timeLeftHours,
  focusShare,
  clockLabel,
  showFocus = true,
}: LifeClockSectographFaceProps) {
  const uid = useId().replace(/:/g, "");
  const dialId = `sg-dial-${uid}`;
  const handTip = polar(R_OUTER - 0.5, currentHour);
  const handHub = polar(R_INNER + 1, currentHour);

  const sectors = activities.filter(
    (a) =>
      a.endHour > a.startHour &&
      !["remaining", "elapsed", "idle"].includes(a.type),
  );

  return (
    <TooltipProvider delayDuration={140}>
      <div className="relative shrink-0" style={{ width: size, height: size }}>
        <svg
          width={size}
          height={size}
          viewBox="0 0 100 100"
          className="w-full h-full drop-shadow-[0_8px_22px_rgba(0,0,0,0.45)]"
          role="img"
          aria-label="Sectograph 24-hour day map"
        >
          <defs>
            <radialGradient id={dialId} cx="40%" cy="35%" r="70%">
              <stop offset="0%" stopColor="#1e293b" />
              <stop offset="100%" stopColor="#020617" />
            </radialGradient>
          </defs>

          {/* Outer rim */}
          <circle cx={CX} cy={CY} r={R_OUTER + 2.8} fill="#334155" fillOpacity={0.45} />
          <circle cx={CX} cy={CY} r={R_OUTER + 1.6} fill="#020617" />

          {/* Day disc */}
          <circle cx={CX} cy={CY} r={R_OUTER} fill={`url(#${dialId})`} />

          {/* Faint elapsed pie (now → midnight behind) */}
          {currentHour > 0.08 && (
            <path
              d={sectorPath(R_INNER, R_OUTER, 0, Math.min(24, currentHour))}
              fill="rgba(148,163,184,0.06)"
              className="pointer-events-none"
            />
          )}

          {/* Hour ticks */}
          {Array.from({ length: 24 }, (_, h) => {
            const major = h % 6 === 0;
            const a = polar(R_OUTER - (major ? 0 : 0.2), h);
            const b = polar(R_OUTER + (major ? 2.2 : 1.2), h);
            return (
              <line
                key={h}
                x1={a.x}
                y1={a.y}
                x2={b.x}
                y2={b.y}
                stroke={major ? "rgba(248,250,252,0.5)" : "rgba(248,250,252,0.18)"}
                strokeWidth={major ? 1 : 0.5}
                strokeLinecap="round"
              />
            );
          })}

          {/* Activity sectors */}
          {sectors.map((a, idx) => {
            const gap = a.endHour - a.startHour > 0.2 ? 0.03 : 0.01;
            const d = sectorPath(R_INNER, R_OUTER - 0.4, a.startHour + gap, a.endHour - gap);
            if (!d) return null;
            const future = a.startHour >= currentHour;
            const tip = `${a.label} · ${formatClockTime(a.startHour)}–${formatClockTime(a.endHour)} · ${formatDuration(a.startHour, a.endHour)}`;
            return (
              <Tooltip key={`${a.type}-${idx}-${a.startHour}`}>
                <TooltipTrigger asChild>
                  <motion.path
                    d={d}
                    fill={a.color}
                    fillOpacity={future ? 0.28 : 0.82}
                    stroke="rgba(2,6,23,0.4)"
                    strokeWidth={0.3}
                    className="cursor-pointer outline-none"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    whileHover={{ fillOpacity: 0.95 }}
                    transition={{ duration: 0.25 }}
                    aria-label={tip}
                    tabIndex={0}
                  />
                </TooltipTrigger>
                <TooltipContent
                  side="top"
                  sideOffset={8}
                  className="border border-white/10 bg-zinc-950/95 text-zinc-50 shadow-xl backdrop-blur-md"
                >
                  <div className="flex items-center gap-2">
                    <span
                      className="h-2 w-2 rounded-full ring-1 ring-white/20"
                      style={{ backgroundColor: a.color }}
                    />
                    <span className="font-medium">{a.label}</span>
                  </div>
                  <p className="mt-0.5 font-mono text-[10px] text-zinc-400 tabular-nums">
                    {formatClockTime(a.startHour)} – {formatClockTime(a.endHour)}
                    <span className="mx-1.5 text-zinc-600">·</span>
                    {formatDuration(a.startHour, a.endHour)}
                  </p>
                </TooltipContent>
              </Tooltip>
            );
          })}

          {/* Quadrant labels */}
          {QUADS.map(({ h, label }) => {
            const p = polar(R_OUTER - 6.5, h);
            return (
              <text
                key={label}
                x={p.x}
                y={p.y}
                textAnchor="middle"
                dominantBaseline="central"
                fill="rgba(148,163,184,0.85)"
                fontSize={compact ? 3 : 3.4}
                fontFamily="ui-monospace, Menlo, monospace"
                fontWeight={600}
                className="pointer-events-none"
              >
                {label}
              </text>
            );
          })}

          {/* Center hub */}
          <circle cx={CX} cy={CY} r={R_INNER - 0.4} fill="#020617" />
          <circle
            cx={CX}
            cy={CY}
            r={R_INNER - 0.4}
            fill="none"
            stroke="rgba(148,163,184,0.2)"
            strokeWidth={0.6}
          />

          {/* Now hand */}
          <line
            x1={handHub.x}
            y1={handHub.y}
            x2={handTip.x}
            y2={handTip.y}
            stroke="#f8fafc"
            strokeWidth={1.35}
            strokeLinecap="round"
            className="pointer-events-none"
          />
          <circle cx={CX} cy={CY} r={2.2} fill="#f8fafc" />
          <circle cx={CX} cy={CY} r={1.1} fill="#2dd4bf" />
          <circle cx={handTip.x} cy={handTip.y} r={1.6} fill="#f8fafc" />
        </svg>

        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none text-center px-6">
          <span
            className={cn(
              "font-mono font-semibold tabular-nums leading-none tracking-tight text-slate-50",
              compact ? "text-sm" : "text-[1.65rem]",
            )}
          >
            {clockLabel}
          </span>
          {showFocus && (
            <>
              <span className="mt-1 text-[9px] font-medium text-slate-400">
                {timeLeftHours.toFixed(1)}h left
              </span>
              <span className="mt-0.5 text-[9px] font-semibold tabular-nums text-teal-400/95">
                {focusShare}% focus
              </span>
            </>
          )}
        </div>
      </div>
    </TooltipProvider>
  );
}
